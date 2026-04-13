import { fireEvent, render, screen } from "@testing-library/react";
import MessageBubble from "./pages/MessageBubble";

const baseMessage = {
  id: 101,
  content: "hello from test",
  timestamp: "2026-04-13T09:00:00Z",
  sender: { id: 1 },
  is_edited: false,
  is_deleted: false,
  reactions: [],
};

describe("MessageBubble", () => {
  test("renders message content and timestamp", () => {
    render(
      <MessageBubble
        m={baseMessage}
        mine={false}
        menuOpenFor={null}
        setMenuOpenFor={() => {}}
        editingMessageId={null}
        editingText=""
        setEditingText={() => {}}
        startEdit={() => {}}
        cancelEdit={() => {}}
        submitEdit={() => {}}
        deleteMessage={() => {}}
        formatTimestamp={() => "Today 09:00"}
        onReact={() => {}}
        currentUserId={1}
      />
    );

    expect(screen.getByText("hello from test")).toBeInTheDocument();
    expect(screen.getByText("Today 09:00")).toBeInTheDocument();
  });

  test("clicking a reaction chip sends reaction callback", () => {
    const onReact = jest.fn();
    const messageWithReaction = {
      ...baseMessage,
      reactions: [{ emoji: "👍", count: 1, users: [1] }],
    };

    render(
      <MessageBubble
        m={messageWithReaction}
        mine={false}
        menuOpenFor={null}
        setMenuOpenFor={() => {}}
        editingMessageId={null}
        editingText=""
        setEditingText={() => {}}
        startEdit={() => {}}
        cancelEdit={() => {}}
        submitEdit={() => {}}
        deleteMessage={() => {}}
        formatTimestamp={() => "Today 09:00"}
        onReact={onReact}
        currentUserId={1}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /👍/i }));
    expect(onReact).toHaveBeenCalledWith(101, "👍");
  });
});
