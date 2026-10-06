// Read a dropped or picked .pbip folder into memory for the in-browser scanner.
import type { DroppedFile } from '../engine/clientScanner';

const WANTED = /\.(tmdl|json|pbir|pbip|pbism|bim)$/i;

export interface ReadFolderResult {
  files: DroppedFile[];
  projectName: string;
}

function projectNameFrom(names: string[], fallback: string): string {
  const pbip = names.find((n) => /\.pbip$/i.test(n));
  if (pbip) return pbip.split('/').pop()!;
  const dir = names.map((n) => n.split('/').find((seg) => /\.(Report|SemanticModel|Dataset)$/i.test(seg))).find(Boolean);
  return dir ? `${dir.replace(/\.(Report|SemanticModel|Dataset)$/i, '')}.pbip` : fallback;
}

/** Files from <input webkitdirectory>. */
export async function readFileList(list: FileList): Promise<ReadFolderResult> {
  const files: DroppedFile[] = [];
  for (const file of Array.from(list)) {
    if (!WANTED.test(file.name)) continue;
    files.push({ name: file.name, path: (file as any).webkitRelativePath || file.name, content: await file.text() });
  }
  return { files, projectName: projectNameFrom(files.map((f) => f.path), 'selected_project.pbip') };
}

/** Read every entry of a directory. readEntries() returns at most ~100 entries per call, so keep calling until it returns none. */
async function readAllEntries(dir: any): Promise<any[]> {
  const reader = dir.createReader();
  const all: any[] = [];
  for (;;) {
    const batch: any[] = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
    if (!batch.length) return all;
    all.push(...batch);
  }
}

/** Items from a drag-and-drop event (folders are walked recursively). */
export async function readDataTransfer(items: DataTransferItemList): Promise<ReadFolderResult> {
  const files: DroppedFile[] = [];
  const walk = async (entry: any, prefix: string): Promise<void> => {
    if (entry.isFile) {
      if (!WANTED.test(entry.name)) return;
      const file: File = await new Promise((resolve, reject) => entry.file(resolve, reject));
      files.push({ name: file.name, path: `${prefix}${file.name}`, content: await file.text() });
    } else if (entry.isDirectory) {
      for (const child of await readAllEntries(entry)) await walk(child, `${prefix}${entry.name}/`);
    }
  };
  const entries = Array.from(items)
    .filter((it) => it.kind === 'file')
    .map((it) => (it.webkitGetAsEntry ? it.webkitGetAsEntry() : null));
  const loose = Array.from(items).filter((it, i) => it.kind === 'file' && !entries[i]).map((it) => it.getAsFile()).filter(Boolean) as File[];
  for (const entry of entries) if (entry) await walk(entry, '');
  for (const f of loose) if (WANTED.test(f.name)) files.push({ name: f.name, path: f.name, content: await f.text() });
  return { files, projectName: projectNameFrom(files.map((f) => f.path), 'uploaded_report.pbip') };
}
