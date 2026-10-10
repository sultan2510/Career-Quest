/** Keep whole-progress writes in order and skip a snapshot replaced while it was waiting. */
export function createSaveQueue() {
  let pending: Promise<void> = Promise.resolve();
  return (save: () => Promise<void>, isCurrent: () => boolean = () => true): Promise<void> => {
    const next = pending.catch(() => {}).then(async () => {
      if (isCurrent()) await save();
    });
    pending = next;
    return next;
  };
}
