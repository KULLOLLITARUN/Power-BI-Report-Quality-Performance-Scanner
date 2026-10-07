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
    files.push({ name: file.name, path: file.webkitRelativePath || file.name, content: await file.text() });
  }
  return { files, projectName: projectNameFrom(files.map((f) => f.path), 'selected_project.pbip') };
}

const isFileEntry = (e: FileSystemEntry): e is FileSystemFileEntry => e.isFile;
const isDirectoryEntry = (e: FileSystemEntry): e is FileSystemDirectoryEntry => e.isDirectory;

/** Read every entry of a directory. readEntries() returns at most ~100 entries per call, so keep calling until it returns none. */
async function readAllEntries(dir: FileSystemDirectoryEntry): Promise<FileSystemEntry[]> {
  const reader = dir.createReader();
  const all: FileSystemEntry[] = [];
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
    if (!batch.length) return all;
    all.push(...batch);
  }
}

/** Items from a drag-and-drop event (folders are walked recursively). */
export async function readDataTransfer(items: DataTransferItemList): Promise<ReadFolderResult> {
  const files: DroppedFile[] = [];
  const walk = async (entry: FileSystemEntry, prefix: string): Promise<void> => {
    if (isFileEntry(entry)) {
      if (!WANTED.test(entry.name)) return;
      const file = await new Promise<File>((resolve, reject) => entry.file(resolve, reject));
      files.push({ name: file.name, path: `${prefix}${file.name}`, content: await file.text() });
    } else if (isDirectoryEntry(entry)) {
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
