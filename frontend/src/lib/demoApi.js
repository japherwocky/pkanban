// Demo API Service - Simulates realistic pkanban CLI commands
// Output formatting matches the actual CLI from pkanban/cli.py

// Initial demo board state
const initialState = {
  board: {
    id: 1,
    name: "Sprint 1",
    columns: [
      {
        id: 1,
        name: "Todo",
        position: 0,
        cards: [
          { id: 1, title: "Setup project structure", columnId: 1, columnName: "Todo", position: 0 }
        ]
      },
      {
        id: 2,
        name: "In Progress",
        position: 1,
        cards: []
      },
      {
        id: 3,
        name: "Done",
        position: 2,
        cards: [
          { id: 2, title: "Configure database", columnId: 3, columnName: "Done", position: 0 },
          { id: 3, title: "Design API schema", columnId: 3, columnName: "Done", position: 1 }
        ]
      }
    ]
  },
  lastCardId: 3
};

// Current state (mutable for demo)
let currentState = JSON.parse(JSON.stringify(initialState));

export function getDemoState() {
  return JSON.parse(JSON.stringify(currentState));
}

export function resetDemo() {
  currentState = JSON.parse(JSON.stringify(initialState));
}

// Parse command string into parts
function parseCommand(cmd) {
  const parts = cmd.trim().split(/\s+/);
  const command = parts[0] || "";
  const args = [];
  const options = {};

  let i = 1;
  while (i < parts.length) {
    const part = parts[i];
    if (part.startsWith("--")) {
      const key = part.slice(2);
      const next = parts[i + 1];
      if (next && !next.startsWith("--")) {
        options[key] = next;
        i += 2;
      } else {
        options[key] = "true";
        i++;
      }
    } else if (part.startsWith("-") && part.length > 1) {
      const key = part.slice(1);
      const next = parts[i + 1];
      if (next && !next.startsWith("--") && !next.startsWith("-")) {
        options[key] = next;
        i += 2;
      } else {
        options[key] = "true";
        i++;
      }
    } else {
      args.push(part);
      i++;
    }
  }

  return { command, args, options };
}

// Generate realistic board get output (matches pkanban/cli.py cmd_board_get)
function formatBoardGet(board) {
  let output = `Board: ${board.name}\n`;
  for (const col of board.columns) {
    output += `  #${col.id} ${col.name} (${col.cards.length} cards)\n`;
    for (const card of col.cards) {
      output += `    - #${card.id} ${card.title}`;
      if (card.description) {
        output += `\n      ${card.description}`;
      }
      output += "\n";
    }
  }
  return output;
}

// Execute a demo command
export function executeCommand(cmd) {
  const { command, args, options } = parseCommand(cmd);

  // Reset state for 'reset' command
  if (command === "reset") {
    currentState = JSON.parse(JSON.stringify(initialState));
    return {
      command,
      stdout: "Demo board reset to initial state",
      exitCode: 0,
      state: JSON.parse(JSON.stringify(currentState))
    };
  }

  // Handle 'pkanban' prefix
  const baseCommand = command === "pkanban" ? args[0] : command;
  const baseArgs = command === "pkanban" ? args.slice(1) : args;

  // Reset state at start of demo sequence
  if (baseCommand === "board" && baseArgs[0] === "get" && baseArgs[1] === "1") {
    currentState = JSON.parse(JSON.stringify(initialState));
  }

  switch (baseCommand) {
    case "board":
      return handleBoardCommand(baseArgs, options);

    case "card":
      return handleCardCommand(baseArgs, options);

    case "help":
      return {
        command,
        stdout: `Available commands:
  pkanban board list                        List all boards
  pkanban board get <board_id>              Show board details
  pkanban card create <column_id> <title>   Create a card
  pkanban card update <card_id> <title>     Update a card
  pkanban help                              Show this help`,
        exitCode: 0
      };

    default:
      return {
        command,
        stderr: `Error: Unknown command '${command}'\nRun 'pkanban help' for usage.`,
        exitCode: 1
      };
  }
}

function handleBoardCommand(args, options) {
  const subCommand = args[0];

  switch (subCommand) {
    case "list":
      return {
        command: "pkanban board list",
        stdout: `   1  Sprint 1`,
        exitCode: 0
      };

    case "get": {
      const boardId = parseInt(args[1]);
      if (isNaN(boardId)) {
        return {
          command: "pkanban board get",
          stderr: "Error: Invalid board ID",
          exitCode: 1
        };
      }
      return {
        command: `pkanban board get ${boardId}`,
        stdout: formatBoardGet(currentState.board),
        exitCode: 0,
        state: JSON.parse(JSON.stringify(currentState))
      };
    }

    case "create":
      return {
        command: "pkanban board create",
        stderr: "Error: Board creation requires a name argument",
        exitCode: 1
      };

    default:
      return {
        command: `pkanban board ${subCommand}`,
        stderr: `Error: Unknown board command '${subCommand}'`,
        exitCode: 1
      };
  }
}

function handleCardCommand(args, options) {
  const subCommand = args[0];

  switch (subCommand) {
    case "create": {
      const columnId = parseInt(args[1]);
      const title = args.slice(2).join(" ");

      if (isNaN(columnId) || !title) {
        return {
          command: "pkanban card create",
          stderr: "Error: Missing required arguments. Usage: pkanban card create <column_id> <title>",
          exitCode: 1
        };
      }

      // Find column
      const column = currentState.board.columns.find(c => c.id === columnId);
      if (!column) {
        return {
          command: `pkanban card create ${columnId} ${title}`,
          stderr: `Error: Column ${columnId} not found`,
          exitCode: 1
        };
      }

      // Create card
      currentState.lastCardId++;
      const newCard = {
        id: currentState.lastCardId,
        title,
        columnId,
        columnName: column.name,
        position: column.cards.length
      };
      column.cards.push(newCard);

      return {
        command: `pkanban card create ${columnId} ${title}`,
        stdout: `Card created with id=${newCard.id}`,
        exitCode: 0,
        state: JSON.parse(JSON.stringify(currentState))
      };
    }

    case "update": {
      const cardId = parseInt(args[1]);
      const title = args.slice(2).join(" ").split(" --")[0];

      if (isNaN(cardId) || !title) {
        return {
          command: "pkanban card update",
          stderr: "Error: Missing required arguments. Usage: pkanban card update <card_id> <title>",
          exitCode: 1
        };
      }

      // Find card across all columns
      let card;
      let fromColumn;
      for (const col of currentState.board.columns) {
        const found = col.cards.find(c => c.id === cardId);
        if (found) {
          card = found;
          fromColumn = col;
          break;
        }
      }

      if (!card) {
        return {
          command: `pkanban card update ${cardId} ${title}`,
          stderr: `Error: Card ${cardId} not found`,
          exitCode: 1
        };
      }

      // Handle column move
      const newColumnId = options["column"] || options["c"];
      if (newColumnId) {
        const newColumn = currentState.board.columns.find(c => c.id === parseInt(newColumnId));
        if (!newColumn) {
          return {
            command: `pkanban card update ${cardId} ${title}`,
            stderr: `Error: Column ${newColumnId} not found`,
            exitCode: 1
          };
        }

        // Move card between columns
        if (fromColumn && fromColumn.id !== newColumn.id) {
          fromColumn.cards = fromColumn.cards.filter(c => c.id !== cardId);
          card.columnId = newColumn.id;
          card.columnName = newColumn.name;
          newColumn.cards.push(card);
        }
      }

      // Update title
      card.title = title;

      // Handle description
      const description = options["description"] || options["d"];
      if (description !== undefined) {
        card.description = description;
      }

      return {
        command: `pkanban card update ${cardId} ${title}${newColumnId ? ` --column ${newColumnId}` : ""}${description ? ` --description "${description}"` : ""}`,
        stdout: "Card updated",
        exitCode: 0,
        state: JSON.parse(JSON.stringify(currentState))
      };
    }

    case "delete": {
      const cardId = parseInt(args[1]);
      if (isNaN(cardId)) {
        return {
          command: "pkanban card delete",
          stderr: "Error: Missing card ID",
          exitCode: 1
        };
      }

      // Find and delete card
      for (const col of currentState.board.columns) {
        const idx = col.cards.findIndex(c => c.id === cardId);
        if (idx !== -1) {
          col.cards.splice(idx, 1);
          return {
            command: `pkanban card delete ${cardId}`,
            stdout: "Card deleted",
            exitCode: 0,
            state: JSON.parse(JSON.stringify(currentState))
          };
        }
      }

      return {
        command: `pkanban card delete ${cardId}`,
        stderr: `Error: Card ${cardId} not found`,
        exitCode: 1
      };
    }

    default:
      return {
        command: `pkanban card ${subCommand}`,
        stderr: `Error: Unknown card command '${subCommand}'`,
        exitCode: 1
      };
  }
}
