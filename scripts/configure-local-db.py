"""Create a project-owned PostgreSQL cluster, configure CareerQuest and seed it.

Run with the project's Python environment. Secrets remain in ignored files and
process memory; neither passwords nor connection strings are printed.
"""
import argparse
import asyncio
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from urllib.parse import quote, unquote, urlparse

import asyncpg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(program, *arguments, required=True):
    if program.name == 'pg_ctl.exe' and 'start' in arguments:
        # Windows PostgreSQL descendants can retain inherited output handles.
        # A file avoids waiting for an EOF from a server intended to stay alive.
        with (ROOT / '.local' / 'postgres' / 'control.log').open('a', encoding='utf-8') as control:
            result = subprocess.run([str(program), *map(str, arguments)], cwd=ROOT,
                                    stdout=control, stderr=subprocess.STDOUT, timeout=60)
        if required and result.returncode:
            raise RuntimeError('PostgreSQL startup failed. Inspect .local/postgres/control.log privately.')
        return result
    result = subprocess.run([str(program), *map(str, arguments)], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if required and result.returncode:
        # These tools receive the password through a file, never arguments.
        raise RuntimeError(f'{program.name} failed: {result.stderr.strip() or result.stdout.strip()}')
    return result


def configure(port):
    env_path = ROOT / 'backend' / '.env'
    values = dict(dotenv_values(env_path)) if env_path.exists() else {}
    if values.get('DATABASE_URL'):
        parsed = urlparse(values['DATABASE_URL'])
        if parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.port != port or parsed.path != '/careerquest':
            raise RuntimeError('backend/.env already targets another database. Existing configuration was preserved.')
        username, password = unquote(parsed.username or ''), unquote(parsed.password or '')
        if username != 'careerquest' or not password:
            raise RuntimeError('Existing local database credentials are incomplete; configuration was preserved.')
    else:
        username, password = 'careerquest', secrets.token_urlsafe(32)
        values['DATABASE_URL'] = f'postgresql://{username}:{quote(password, safe="")}@127.0.0.1:{port}/careerquest'
    if len(values.get('JWT_SECRET') or '') < 32:
        values['JWT_SECRET'] = secrets.token_urlsafe(48)
    values.update(FRONTEND_URL='http://localhost:3000', COOKIE_SECURE='false', COOKIE_SAMESITE='lax')
    values.setdefault('SMTP_HOST', '')
    values.setdefault('ANTHROPIC_API_KEY', '')
    values.setdefault('ANTHROPIC_MODEL', 'claude-sonnet-5-5')
    # Keep quoted/custom provider settings intact when already configured.
    lines = ['# Local CareerQuest configuration. Keep this ignored file private.']
    for key, value in values.items():
        if value is not None:
            escaped = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            lines.append(f'{key}="{escaped}"')
    env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return username, password


async def apply_schema(username, password, port):
    admin = await asyncpg.connect(host='127.0.0.1', port=port, user=username,
                                  password=password, database='postgres', timeout=15)
    try:
        if not await admin.fetchval('select 1 from pg_database where datname=$1', 'careerquest'):
            await admin.execute('create database careerquest')
    finally:
        await admin.close()
    connection = await asyncpg.connect(host='127.0.0.1', port=port, user=username,
                                       password=password, database='careerquest', timeout=15)
    try:
        async with connection.transaction():
            await connection.execute((ROOT / 'backend' / 'schema.sql').read_text(encoding='utf-8'))
        from backend.ingest import ingest
        await ingest(connection)
        tables = await connection.fetchval("select count(*) from information_schema.tables where table_schema='public'")
        chunks = await connection.fetchval('select count(*) from rag_chunks')
        await connection.execute('select 1')
        print(f'Connected to careerquest on 127.0.0.1:{port}; {tables} tables and {chunks} knowledge passages ready.')
    finally:
        await connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgres-bin', default='C:/Program Files/PostgreSQL/18/bin')
    parser.add_argument('--port', type=int, default=5433)
    args = parser.parse_args()
    pg_bin = Path(args.postgres_bin).resolve()
    if not (pg_bin / 'initdb.exe').exists():
        raise RuntimeError('PostgreSQL binaries were not found. Supply --postgres-bin with their directory.')
    local_dir = ROOT / '.local' / 'postgres'
    local_dir.mkdir(parents=True, exist_ok=True)
    data_dir = local_dir / 'data'
    username, password = configure(args.port)
    if not (data_dir / 'PG_VERSION').exists():
        # An incomplete initialization is retained for inspection, never erased.
        if data_dir.exists() and any(data_dir.iterdir()):
            raise RuntimeError('The project cluster directory is not empty; existing contents were preserved.')
        password_path = local_dir / f'.init-password-{secrets.token_hex(8)}'
        password_path.write_text(password + '\n', encoding='utf-8')
        try:
            run(pg_bin / 'initdb.exe', '-D', data_dir, '-U', username,
                '--pwfile', password_path, '--auth-host=scram-sha-256', '--auth-local=scram-sha-256',
                '--encoding=UTF8', '--locale=C')
        finally:
            password_path.unlink(missing_ok=True)
        print('Initialized a dedicated project database cluster.')
    running = False
    pid_path = data_dir / 'postmaster.pid'
    if pid_path.exists():
        pid_lines = pid_path.read_text(encoding='utf-8').splitlines()
        if Path(pid_lines[1]).resolve() != data_dir.resolve() or int(pid_lines[3]) != args.port:
            raise RuntimeError('The cluster process metadata does not match this project and port.')
        running = run(pg_bin / 'pg_isready.exe', '-h', '127.0.0.1', '-p', args.port, required=False).returncode == 0
    if not running:
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', args.port)) == 0:
                raise RuntimeError(f'Port {args.port} is used by another process; it was left unchanged.')
        run(pg_bin / 'pg_ctl.exe', '-D', data_dir, '-l', local_dir / 'server.log',
            '-o', f'-h 127.0.0.1 -p {args.port}', '-w', 'start')
        print('Started the project PostgreSQL server on the loopback interface.')
    asyncio.run(apply_schema(username, password, args.port))
    print('Local database and JWT credentials saved in backend/.env (values withheld).')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Database/server exceptions can contain configuration details. Only
        # tool initialization messages above are designed for direct display.
        if isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        else:
            print(f'Local setup failed ({type(error).__name__}); no credentials were printed.', file=sys.stderr)
        sys.exit(1)
