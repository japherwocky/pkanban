# Connect an AI app (MCP)

pkanban is an MCP server as well as a CLI, so AI apps that can't run commands
can use your boards too: the Claude and ChatGPT chat apps among them. Once
connected, the app reads your boards and cards, adds and moves cards, and
comments, all as you, and you see every change on the board.

If your AI can run commands (Claude Code, Codex, opencode, Cursor), the CLI is
the simpler route: see the [Quick Start](/docs/quickstart). The connector works
there too, if you'd rather.

The address to give an app is:

```
https://pkanban.pearachute.com/mcp
```

On a self-hosted server, it's your server's own address with `/mcp` on the end.

## Claude

In Claude, open **Settings › Connectors**, choose **Add custom connector**,
name it `pkanban`, and paste the address. Click **Add**, then **Connect**, and
approve on the pkanban page that opens. Claude on the web and Claude Desktop
share connectors, so you do this once.

There's a walkthrough with example requests at
[pkanban.pearachute.com/connect/claude](https://pkanban.pearachute.com/connect/claude).

## ChatGPT

ChatGPT connects to custom MCP servers in **Developer mode**. OpenAI has moved
these settings more than once, so the labels may differ from what's here:

1. Turn on Developer mode in ChatGPT's settings. Look under **Apps &
   Connectors › Advanced**, or under **Security**.
2. Create a connector with the address above. Choose **OAuth** for
   authentication and leave the client ID and secret empty: pkanban registers
   ChatGPT itself.
3. Sign in to pkanban when ChatGPT sends you there, check that the page says it
   is sending you back to ChatGPT's own site, and approve.

Which ChatGPT plans offer Developer mode, and whether they allow tools that
change things, is up to OpenAI and has changed over time.

## Claude Code, Cursor and other apps you configure yourself

**Signing in through the browser.** Apps that support MCP sign-in only need
the address. In Claude Code:

```bash
claude mcp add --transport http pkanban https://pkanban.pearachute.com/mcp
```

Then run `/mcp` in Claude Code, pick pkanban, and choose **Authenticate**.

**With an API key.** Any app that lets you set a header can use a key instead.
Make one under Settings › API keys, or with `pkanban apikey create "Cursor"`,
and send it as `X-API-Key` or as `Authorization: Bearer`. For Cursor, in
`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "pkanban": {
      "url": "https://pkanban.pearachute.com/mcp",
      "headers": { "X-API-Key": "pkanban_..." }
    }
  }
}
```

Other apps differ in where remote MCP servers go; pkanban needs only the
address and the key.

## What a connected app can do

| Tool | What it does |
| --- | --- |
| `list_boards` | Lists the boards you can see |
| `get_board` | A board's columns, with each card's id and title |
| `get_card` | One card in full: description, comments, board and column |
| `search_cards` | Finds cards by the words in them, archived ones included |
| `create_board` | Makes a board, with the default columns |
| `create_column` | Adds a column to a board |
| `create_card` | Adds a card to a column |
| `update_card` | Changes a card's title or description |
| `move_card` | Moves a card to another column, or within its column |
| `add_comment` | Comments on a card |
| `archive_card` | Hides a card from its board; search still finds it |
| `unarchive_card` | Brings an archived card back |

- **It works as you.** It sees the boards you can see, and nothing else.
- **Your plan's limits apply**, as in the CLI. Past one, the app gets an error
  with the upgrade link, and nothing is lost.
- **Nothing can be deleted** through it. Archiving stands in, and can be
  undone. Teams, sharing, API keys and your plan are out of its reach --
  including inviting people to a board, which sends mail to an address and
  gives it access. A board's text is written by whoever can see it, so a tool
  that could invite would be one a hostile card could ask for. Invite from the
  web or the CLI.
- **Card text is written by whoever can see the board.** The connector tells
  the app to treat it as content, not instructions. Still, think twice before
  letting an AI act on a board strangers can write to.

## Disconnecting

A connected app's access is an API key named after it, such as
`Claude (connected app)`. Revoke that key under Settings › API keys and the app
is cut off at once. Remove the connector in the app too, so it stops offering
pkanban's tools.

## Self-hosting

- The address is your server's own `/mcp`, and the sign-in pages and
  discovery documents name your server, not the hosted one. Nothing needs
  registering with Anthropic or OpenAI.
- Claude's and ChatGPT's chat apps connect from their companies' servers, so
  yours has to be reachable from the internet over HTTPS for them.
- On a private network, use an app that connects from your own computer
  (Claude Code, Cursor) with an API key.

## How it works

For the curious, or anyone writing a client:

- **Transport.** Streamable HTTP at `/mcp`, stateless, with JSON responses.
  `GET /mcp` answers 405: there is no event stream.
- **Authentication.** Every request needs an API key, as `X-API-Key` or
  `Authorization: Bearer`. Without one, `/mcp` answers 401 with a
  `WWW-Authenticate` header pointing at
  `/.well-known/oauth-protected-resource/mcp`.
- **OAuth 2.1.** pkanban is its own authorization server: metadata at
  `/.well-known/oauth-authorization-server`, dynamic client registration at
  `/oauth/register`, authorization code with PKCE (S256) at `/oauth/authorize`,
  and tokens from `/oauth/token`. The token is a new API key. There are no
  refresh tokens, because keys don't expire until revoked.
- **Tools** call the same REST API the CLI uses, with your key, so access
  checks and limits are identical by construction.
