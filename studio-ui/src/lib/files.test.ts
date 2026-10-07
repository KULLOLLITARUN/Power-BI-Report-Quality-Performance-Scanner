import { describe, expect, it } from 'vitest';
import { readDataTransfer, readFileList } from './files';

// Minimal stand-ins for the browser's File System entries and DataTransferItemList.
type Tree = { [name: string]: string | Tree };

function fileEntry(name: string, content: string) {
  return {
    isFile: true, isDirectory: false, name,
    file: (resolve: (f: File) => void) => resolve(new File([content], name)),
  };
}

/** A directory whose reader hands out entries `batch` at a time, like Chromium's 100-entry pages. */
function dirEntry(name: string, tree: Tree, batch = 100): unknown {
  const children = Object.entries(tree).map(([n, v]) => (typeof v === 'string' ? fileEntry(n, v) : dirEntry(n, v, batch)));
  return {
    isFile: false, isDirectory: true, name,
    createReader: () => {
      let at = 0;
      return {
        readEntries: (resolve: (e: unknown[]) => void) => {
          const page = children.slice(at, at + batch);
          at += page.length;
          resolve(page);
        },
      };
    },
  };
}

function items(entries: unknown[], loose: File[] = []): DataTransferItemList {
  const list = [
    ...entries.map((e) => ({ kind: 'file', webkitGetAsEntry: () => e, getAsFile: () => null })),
    ...loose.map((f) => ({ kind: 'file', webkitGetAsEntry: () => null, getAsFile: () => f })),
    { kind: 'string', webkitGetAsEntry: () => null, getAsFile: () => null },
  ];
  return list as unknown as DataTransferItemList;
}

const project: Tree = {
  'Sales.pbip': '{}',
  'Sales.SemanticModel': { definition: { tables: { 'Sales.tmdl': 'table Sales', 'notes.txt': 'skip me' }, 'model.tmdl': 'model' } },
  'Sales.Report': { 'report.json': '{}', 'StaticResources': { 'logo.png': 'binary' } },
};

describe('readDataTransfer (drag and drop)', () => {
  it('walks a dropped project folder and keeps only project files, with their paths', async () => {
    const out = await readDataTransfer(items([dirEntry('Sales', project)]));
    expect(out.projectName).toBe('Sales.pbip');
    expect(out.files.map((f) => f.path).sort()).toEqual([
      'Sales/Sales.Report/report.json',
      'Sales/Sales.SemanticModel/definition/model.tmdl',
      'Sales/Sales.SemanticModel/definition/tables/Sales.tmdl',
      'Sales/Sales.pbip',
    ]);
    expect(out.files.find((f) => f.name === 'Sales.tmdl')?.content).toBe('table Sales');
  });

  it('reads folders with more entries than one readEntries() page', async () => {
    const tables: Tree = {};
    for (let i = 0; i < 250; i++) tables[`T${i}.tmdl`] = `table T${i}`;
    const out = await readDataTransfer(items([dirEntry('Big.SemanticModel', { definition: { tables } }, 100)]));
    expect(out.files).toHaveLength(250);
    expect(out.projectName).toBe('Big.pbip');
  });

  it('accepts loose files dropped without a folder', async () => {
    const out = await readDataTransfer(items([], [new File(['{}'], 'model.bim'), new File(['x'], 'readme.md')]));
    expect(out.files.map((f) => f.path)).toEqual(['model.bim']);
    expect(out.projectName).toBe('uploaded_report.pbip');
  });

  it('returns no files for a folder with nothing to scan', async () => {
    const out = await readDataTransfer(items([dirEntry('Photos', { 'a.jpg': '', 'b.png': '' })]));
    expect(out.files).toEqual([]);
  });
});

describe('readFileList (folder picker)', () => {
  it('uses webkitRelativePath and skips other files', async () => {
    const withPath = (content: string, name: string, path: string) => {
      const f = new File([content], name);
      Object.defineProperty(f, 'webkitRelativePath', { value: path });
      return f;
    };
    const list = [withPath('{}', 'Sales.pbip', 'Sales/Sales.pbip'), withPath('t', 'Sales.tmdl', 'Sales/x/Sales.tmdl'), withPath('', 'a.png', 'Sales/a.png')];
    const out = await readFileList(list as unknown as FileList);
    expect(out.files.map((f) => f.path)).toEqual(['Sales/Sales.pbip', 'Sales/x/Sales.tmdl']);
    expect(out.projectName).toBe('Sales.pbip');
  });
});
