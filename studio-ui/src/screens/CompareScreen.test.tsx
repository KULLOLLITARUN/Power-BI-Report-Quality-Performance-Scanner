// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { JsonDropzone } from './CompareScreen';

const mockToast = vi.fn();
vi.mock('../components/ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../components/ui')>();
  return {
    ...actual,
    useToast: () => mockToast,
  };
});

describe('JsonDropzone Component', () => {
  const defaultProps = {
    id: 'cmp-test',
    label: 'Baseline',
    sublabel: 'Previous scan',
    placeholder: 'Drop json here',
    value: '',
    data: null,
    onClear: vi.fn(),
    onFileLoaded: vi.fn(),
    onChangeText: vi.fn(),
    onBrowse: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('stops event propagation on drop so window listener is not called', async () => {
    const windowDropListener = vi.fn();
    window.addEventListener('drop', windowDropListener);

    const onFileLoaded = vi.fn();
    const { container } = render(<JsonDropzone {...defaultProps} onFileLoaded={onFileLoaded} />);
    const dropzone = container.querySelector('.cmp-dropzone')!;

    const file = {
      name: 'scan.json',
      text: vi.fn(async () => JSON.stringify({ report_name: 'Sales', findings: [{ rule_id: 'D01' }] })),
    } as unknown as File;

    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
        types: ['Files'],
      },
    });

    expect(windowDropListener).not.toHaveBeenCalled();

    // Await async handleFile resolution so no pending promises bleed
    await waitFor(() => {
      expect(onFileLoaded).toHaveBeenCalled();
    });

    window.removeEventListener('drop', windowDropListener);
  });

  it('preserves dragging highlight through child dragenter and dragleave events', () => {
    const { container } = render(<JsonDropzone {...defaultProps} />);
    const dropzone = container.querySelector('.cmp-dropzone')!;
    const input = container.querySelector('input.input')!;

    expect(dropzone.classList.contains('dragging')).toBe(false);

    // Enter dropzone card
    fireEvent.dragEnter(dropzone, {
      dataTransfer: { types: ['Files'] },
    });
    expect(dropzone.classList.contains('dragging')).toBe(true);

    // Move cursor over child input inside dropzone (fires dragEnter on child)
    fireEvent.dragEnter(input, {
      dataTransfer: { types: ['Files'] },
    });
    expect(dropzone.classList.contains('dragging')).toBe(true);

    // Leave event from transition between parent and child
    fireEvent.dragLeave(dropzone, {
      dataTransfer: { types: ['Files'] },
    });
    // Depth counter remains > 0, so dragging class persists
    expect(dropzone.classList.contains('dragging')).toBe(true);

    // Cursor leaves card completely
    fireEvent.dragLeave(dropzone, {
      dataTransfer: { types: ['Files'] },
    });
    expect(dropzone.classList.contains('dragging')).toBe(false);
  });

  it('rejects non-JSON drops and notes ignored files', () => {
    const onFileLoaded = vi.fn();
    const { container } = render(<JsonDropzone {...defaultProps} onFileLoaded={onFileLoaded} />);
    const dropzone = container.querySelector('.cmp-dropzone')!;

    const file1 = { name: 'report.pbip', text: vi.fn(async () => 'text') } as unknown as File;
    const file2 = { name: 'extra.json', text: vi.fn(async () => '{}') } as unknown as File;

    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file1, file2],
        types: ['Files'],
      },
    });

    expect(onFileLoaded).not.toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith(
      expect.stringContaining('Only .json audit files can be dropped here'),
      'error'
    );
    expect(mockToast).toHaveBeenCalledWith(
      expect.stringContaining('1 other file(s) ignored'),
      'error'
    );
  });

  it('includes note on multiple dropped files when valid', async () => {
    const onFileLoaded = vi.fn();
    const { container } = render(<JsonDropzone {...defaultProps} onFileLoaded={onFileLoaded} />);
    const dropzone = container.querySelector('.cmp-dropzone')!;

    const validJson = JSON.stringify({ report_name: 'Test', findings: [{ rule_id: 'R01' }] });
    const file1 = { name: 'valid.json', text: vi.fn(async () => validJson) } as unknown as File;
    const file2 = { name: 'second.json', text: vi.fn(async () => validJson) } as unknown as File;

    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file1, file2],
        types: ['Files'],
      },
    });

    await waitFor(() => {
      expect(onFileLoaded).toHaveBeenCalled();
    });

    expect(mockToast).toHaveBeenCalledWith(
      expect.stringContaining('1 other file(s) ignored'),
      'info'
    );
  });

  it('discards pending file read if user clicks clear before read resolves', async () => {
    const onFileLoaded = vi.fn();
    const onClear = vi.fn();
    let resolveDelayedRead: (val: string) => void = () => {};

    const delayedPromise = new Promise<string>((resolve) => {
      resolveDelayedRead = resolve;
    });

    const mockSlowFile = {
      name: 'large_scan.json',
      text: vi.fn(() => delayedPromise),
    } as unknown as File;

    const { container } = render(
      <JsonDropzone
        {...defaultProps}
        onFileLoaded={onFileLoaded}
        onClear={onClear}
        data={{ report_name: 'Old Report', findings: [{ rule_id: 'R0' }] }}
      />
    );
    const dropzone = container.querySelector('.cmp-dropzone')!;

    // Start dropping the slow file
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [mockSlowFile],
        types: ['Files'],
      },
    });

    // Confirm that the read actually started
    expect(mockSlowFile.text).toHaveBeenCalledTimes(1);

    // While read is pending, click Clear button
    const clearBtn = container.querySelector('button[title="Clear JSON"]')!;
    fireEvent.click(clearBtn);
    expect(onClear).toHaveBeenCalled();

    // Now resolve the delayed file.text()
    resolveDelayedRead(JSON.stringify({ report_name: 'Delayed Report', findings: [{ rule_id: 'R1' }] }));

    // Wait a macro-task tick
    await new Promise((r) => setTimeout(r, 20));

    // Stale read must be ignored due to loadSeq invalidation
    expect(onFileLoaded).not.toHaveBeenCalled();
  });

  it('discards pending file read if user edits path input before read resolves', async () => {
    const onFileLoaded = vi.fn();
    const onChangeText = vi.fn();
    let resolveDelayedRead: (val: string) => void = () => {};

    const delayedPromise = new Promise<string>((resolve) => {
      resolveDelayedRead = resolve;
    });

    const mockSlowFile = {
      name: 'large_scan.json',
      text: vi.fn(() => delayedPromise),
    } as unknown as File;

    const { container } = render(
      <JsonDropzone
        {...defaultProps}
        onFileLoaded={onFileLoaded}
        onChangeText={onChangeText}
      />
    );
    const dropzone = container.querySelector('.cmp-dropzone')!;
    const input = container.querySelector('input.input')!;

    // Start dropping the slow file
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [mockSlowFile],
        types: ['Files'],
      },
    });

    // Confirm that the read actually started
    expect(mockSlowFile.text).toHaveBeenCalledTimes(1);

    // While read is pending, user types in the path input
    fireEvent.change(input, { target: { value: 'C:\\Manual\\Path.pbip' } });
    expect(onChangeText).toHaveBeenCalledWith('C:\\Manual\\Path.pbip');

    // Now resolve the delayed file.text()
    resolveDelayedRead(JSON.stringify({ report_name: 'Delayed Report', findings: [{ rule_id: 'R1' }] }));

    // Wait a macro-task tick
    await new Promise((r) => setTimeout(r, 20));

    // Stale read must be ignored due to loadSeq invalidation
    expect(onFileLoaded).not.toHaveBeenCalled();
  });
});
