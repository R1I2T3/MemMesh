export interface Message {
  message_id: string;
  session_id: string;
  parent_message_id: string | null;
  role: 'user' | 'assistant' | string;
  content: string;
  created_at: string | null;
}

/**
 * Finds all leaf messages in a list of messages.
 * A leaf is a message that is not a parent of any other message.
 */
export function getLeafMessages(messages: Message[]): Message[] {
  const parentIds = new Set(
    messages
      .map((m) => m.parent_message_id)
      .filter((id): id is string => id !== null)
  );
  return messages.filter((m) => !parentIds.has(m.message_id));
}

/**
 * Reconstructs the active path from the root to the given active leaf message.
 * Traces upwards using parent_message_id until the root is reached, then reverses.
 */
export function reconstructActivePath(
  messages: Message[],
  activeMessageId: string | null
): Message[] {
  if (!activeMessageId || messages.length === 0) return [];
  const messageMap = new Map(messages.map((m) => [m.message_id, m]));
  const path: Message[] = [];
  let currId: string | null = activeMessageId;
  const visited = new Set<string>();

  while (currId) {
    if (visited.has(currId)) {
      break; // Circular reference protection
    }
    visited.add(currId);
    const msg = messageMap.get(currId);
    if (!msg) break;
    path.push(msg);
    currId = msg.parent_message_id;
  }
  return path.reverse();
}

/**
 * Finds the latest leaf message ID in the whole message set or under a specific sub-branch.
 */
export function findLatestLeaf(messages: Message[], startMessageId: string): string {
  // Build parent-child relationships
  const childrenMap = new Map<string, Message[]>();
  messages.forEach((m) => {
    if (m.parent_message_id) {
      const list = childrenMap.get(m.parent_message_id) || [];
      list.push(m);
      childrenMap.set(m.parent_message_id, list);
    }
  });

  let currentId = startMessageId;
  const visited = new Set<string>();
  while (true) {
    if (visited.has(currentId)) {
      break; // Circular reference protection
    }
    visited.add(currentId);
    const children = childrenMap.get(currentId) || [];
    if (children.length === 0) {
      return currentId;
    }
    // Sort/pick the last child in chronological or default order
    const nextChild = children[children.length - 1];
    currentId = nextChild.message_id;
  }
  return currentId;
}
