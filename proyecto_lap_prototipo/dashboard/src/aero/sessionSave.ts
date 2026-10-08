export interface SaveFeedback {
  started: () => void;
  saved: () => void;
  failed: (message: string) => void;
  finished: () => void;
}

/** Serialize writes from this session so response order also matches the
 * configuration committed by the backend. A rejected request cannot poison
 * later saves, and queued drafts never follow the user into another project. */
export class ConfigSaveQueue {
  private tail: Promise<void> = Promise.resolve();

  enqueue<T>(draft: T, canWrite: () => boolean, send: (snapshot: T) => Promise<unknown>): Promise<void> {
    const payload = JSON.stringify(draft);
    const operation = this.tail.then(async () => {
      if (!canWrite()) throw new Error('El proyecto cambió antes de guardar. Este borrador no se envió.');
      await send(JSON.parse(payload) as T);
    });
    this.tail = operation.then(() => {}, () => {});
    return operation;
  }
}

// Explicit save and autosave share the same error/dirty-state contract.
export async function saveWithFeedback(operation: () => Promise<unknown>, feedback: SaveFeedback): Promise<void> {
  feedback.started();
  try {
    await operation();
    feedback.saved();
  } catch (error) {
    feedback.failed(error instanceof Error ? error.message : String(error));
    throw error;
  } finally {
    feedback.finished();
  }
}

export function saveStatusLabel(error: string, saving: boolean, dirty: boolean): string {
  return saving ? 'Guardando…' : error ? 'No se pudo guardar' : dirty ? 'Cambios sin guardar' : 'Guardado';
}
