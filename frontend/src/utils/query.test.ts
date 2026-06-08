import { expect, test, describe } from 'vitest';
import { getLeafMessages, reconstructActivePath, findLatestLeaf, Message } from './query';

describe('Chat branching utilities', () => {
  const messages: Message[] = [
    { message_id: 'm1', session_id: 'sess-1', parent_message_id: null, role: 'user', content: 'hello', created_at: null },
    { message_id: 'm2', session_id: 'sess-1', parent_message_id: 'm1', role: 'assistant', content: 'hi there', created_at: null },
    // Branch A
    { message_id: 'm3_a', session_id: 'sess-1', parent_message_id: 'm2', role: 'user', content: 'tell me about A', created_at: null },
    { message_id: 'm4_a', session_id: 'sess-1', parent_message_id: 'm3_a', role: 'assistant', content: 'A is great', created_at: null },
    // Branch B (started from m2)
    { message_id: 'm3_b', session_id: 'sess-1', parent_message_id: 'm2', role: 'user', content: 'tell me about B', created_at: null },
    { message_id: 'm4_b', session_id: 'sess-1', parent_message_id: 'm3_b', role: 'assistant', content: 'B is cool', created_at: null },
  ];

  test('getLeafMessages identifies all leaves in the message tree', () => {
    const leaves = getLeafMessages(messages);
    const leafIds = leaves.map(l => l.message_id);
    expect(leafIds).toContain('m4_a');
    expect(leafIds).toContain('m4_b');
    expect(leafIds).not.toContain('m2');
    expect(leafIds).not.toContain('m1');
    expect(leaves.length).toBe(2);
  });

  test('reconstructActivePath builds full path from leaf to root in chronological order', () => {
    const pathA = reconstructActivePath(messages, 'm4_a');
    const pathAIds = pathA.map(p => p.message_id);
    expect(pathAIds).toEqual(['m1', 'm2', 'm3_a', 'm4_a']);

    const pathB = reconstructActivePath(messages, 'm4_b');
    const pathBIds = pathB.map(p => p.message_id);
    expect(pathBIds).toEqual(['m1', 'm2', 'm3_b', 'm4_b']);
  });

  test('reconstructActivePath handles null activeMessageId gracefully', () => {
    expect(reconstructActivePath(messages, null)).toEqual([]);
  });

  test('findLatestLeaf traverses down to the correct leaf message', () => {
    const leafA = findLatestLeaf(messages, 'm3_a');
    expect(leafA).toBe('m4_a');

    const leafB = findLatestLeaf(messages, 'm3_b');
    expect(leafB).toBe('m4_b');

    // From the root, picking the latest child path (by default the last item added, which is branch B)
    const leafRoot = findLatestLeaf(messages, 'm1');
    expect(leafRoot).toBe('m4_b');
  });
});
