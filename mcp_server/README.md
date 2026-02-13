# Gold Tier MCP Server

Model Context Protocol (MCP) server for the AI Employee, providing external action capabilities: email, LinkedIn posting, and Odoo ERP accounting.

## Tools Available

| Tool | Description | Approval Required |
|------|-------------|-------------------|
| `send_email` | Send emails via SMTP | Yes |
| `post_linkedin` | Publish posts to LinkedIn | Yes |
| `check_email_config` | Verify email configuration and test SMTP connection | No |
| `odoo_accounting` | Create invoices, log payments, get financial reports via Odoo ERP | Invoices/payments: Yes. Reports: No |

## Quick Start

### 1. Install Dependencies

```bash
cd mcp_server
npm install
```

### 2. Configure Credentials (Optional)

For testing, the server runs in **demo/mock mode** automatically when credentials are missing — no setup required.

For production, copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Start the Server

```bash
npm start
# or
node mcp_server.js
```

The server communicates over stdio (standard input/output), which is how Claude Code connects to it.

## Configuration

### SMTP (Email)

**Gmail Setup:**
1. Enable 2-Factor Authentication on your Google Account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the App Password (not your regular password)

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-16-char-app-password
SMTP_FROM=your-email@gmail.com
```

**Other providers:**

| Provider | SMTP Host | Port |
|----------|-----------|------|
| Gmail | smtp.gmail.com | 587 |
| Outlook | smtp-mail.outlook.com | 587 |
| Ethereal (testing) | smtp.ethereal.email | 587 |

Without SMTP credentials, emails run in **mock mode** (logged to console, not sent).

### LinkedIn

1. Go to https://developer.linkedin.com/
2. Create a new app
3. Add the "Share on LinkedIn" product (under Products tab)
4. Generate an OAuth2 access token (under Auth tab)
5. Find your Person URN using the `/v2/me` API endpoint

```env
LINKEDIN_ACCESS_TOKEN=your-access-token
LINKEDIN_PERSON_URN=urn:li:person:your-person-id
```

Without LinkedIn credentials, posts run in **test/demo mode** (logged with simulated post ID, not published).

### Odoo ERP (Gold Tier)

1. Get a free Odoo instance at https://www.odoo.com/trial
2. Install the **Accounting** app from the Apps menu
3. Generate an API key: Settings > Users > your user > Account Security > API Keys > New API Key
4. Note your instance URL and database name

```env
ODOO_URL=https://your-instance.odoo.com
ODOO_DB=your-database-name
ODOO_USERNAME=your-email@example.com
ODOO_API_KEY=your-api-key-here
```

Without Odoo credentials, accounting runs in **test/demo mode** (returns sample financial data).

### X / Twitter (Social Watcher)

Used by `social_watcher.py` (not the MCP server directly), but configured in the same `.env`:

```env
X_BEARER_TOKEN=your-x-bearer-token
```

### Test Mode

Force mock mode for email (log instead of send):

```env
TEST_MODE=true
```

## Connecting to Claude Code

### Option 1: Project `.mcp.json` (Recommended)

The project root already contains a `.mcp.json` file that Claude Code picks up automatically. No manual config needed if you open the project folder in Claude Code.

### Option 2: Claude Code CLI Settings

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "silver-email": {
      "command": "node",
      "args": ["C:\\Hakathon0_ai_employee\\Gold\\mcp_server\\mcp_server.js"]
    }
  }
}
```

### Option 3: Claude Desktop Config

**Windows** — Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gold-tier-mcp": {
      "command": "node",
      "args": ["C:\\Hakathon0_ai_employee\\Gold\\mcp_server\\mcp_server.js"],
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "your-email@gmail.com",
        "SMTP_PASS": "your-app-password",
        "SMTP_FROM": "your-email@gmail.com",
        "ODOO_URL": "https://your-instance.odoo.com",
        "ODOO_DB": "your-database",
        "ODOO_USERNAME": "your-email@example.com",
        "ODOO_API_KEY": "your-api-key"
      }
    }
  }
}
```

**macOS/Linux** — Edit `~/.config/claude/claude_desktop_config.json` with the same format.

## Tool Usage

### send_email

Send an email via SMTP. Requires human approval via `Approval_Check_Skill`.

```json
{
  "to": "recipient@example.com",
  "subject": "Hello from AI Employee",
  "body": "This is a test email.",
  "html": false
}
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `to` | Yes | Recipient email address |
| `subject` | Yes | Email subject line |
| `body` | Yes | Email content (plain text or HTML) |
| `from` | No | Sender address (uses `SMTP_FROM` default) |
| `html` | No | Set to `true` for HTML emails (default: `false`) |

**Validation:**
- Basic email format validation on the `to` address
- All three required fields must be non-empty

### post_linkedin

Post content to LinkedIn. Requires human approval via `Approval_Check_Skill`.

```json
{
  "content": "AI agents are changing how consulting firms operate...",
  "visibility": "PUBLIC"
}
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `content` | Yes | Post text (max 3000 characters) |
| `visibility` | No | `"PUBLIC"` (default) or `"CONNECTIONS"` |

**API:** Uses LinkedIn UGC Posts API (`/v2/ugcPosts`) with `w_member_social` scope.

**Error hints:**
| HTTP Status | Meaning |
|-------------|---------|
| 401 | Access token expired — regenerate it |
| 403 | Missing `w_member_social` scope |
| 422 | Invalid `LINKEDIN_PERSON_URN` format |

### check_email_config

Check SMTP configuration and test the connection. No approval needed.

```json
{}
```

**Returns:**
- `testMode` — whether running in mock mode
- `smtpHost` / `smtpPort` — configured SMTP server
- `hasCredentials` — whether SMTP_USER is set
- `connectionStatus` — `"connected"`, `"error"`, or `"mock"`
- `message` — human-readable status

### odoo_accounting

Manage accounting in Odoo ERP. Supports three actions.

#### create_invoice

Create a new customer invoice (draft). Requires approval.

```json
{
  "action": "create_invoice",
  "customer": "Acme Corp",
  "amount": 5000,
  "description": "Consulting services - February 2026"
}
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `action` | Yes | `"create_invoice"` |
| `customer` | Yes | Customer name (auto-creates partner if not found in Odoo) |
| `amount` | Yes | Invoice amount (must be positive) |
| `description` | No | Line item description (default: `"Services rendered"`) |

**Behavior:**
- Looks up customer by name in Odoo partners; creates a new partner if not found
- Creates a draft invoice (`account.move`, type `out_invoice`) with one line item
- Returns the invoice number, amount, state, and currency

#### log_payment

Record an incoming or outgoing payment. Requires approval.

```json
{
  "action": "log_payment",
  "customer": "Acme Corp",
  "amount": 5000,
  "payment_type": "inbound",
  "description": "Invoice payment received"
}
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `action` | Yes | `"log_payment"` |
| `customer` | Yes | Customer or vendor name |
| `amount` | Yes | Payment amount (must be positive) |
| `payment_type` | No | `"inbound"` (received, default) or `"outbound"` (sent) |
| `description` | No | Payment memo |

**Behavior:**
- Automatically selects bank journal
- Sets `partner_type` based on payment direction (`customer` for inbound, `supplier` for outbound)
- Returns payment name, amount, state, and type

#### get_report

Retrieve a financial summary. Read-only, no approval needed.

```json
{
  "action": "get_report",
  "report_type": "summary",
  "date_from": "2026-01-01",
  "date_to": "2026-02-13"
}
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `action` | Yes | `"get_report"` |
| `report_type` | No | `"summary"` (default), `"revenue_weekly"`, `"revenue_monthly"`, `"expenses_weekly"`, or `"expenses_monthly"` |
| `date_from` | No | Start date `YYYY-MM-DD` (default: 7 days ago for weekly, 30 days for others) |
| `date_to` | No | End date `YYYY-MM-DD` (default: today) |

**Returns:**
- `total_revenue` / `total_expenses` / `net_profit`
- `invoice_count` / `bill_count` / `payment_count`
- `top_customers` — top 5 by revenue
- `recent_invoices` — last 5 invoices with number, customer, amount, date, state
- `recent_bills` — last 5 vendor bills

**Data sources:** Reads `account.move` (invoices/bills) and `account.payment` records from Odoo via JSON-RPC.

## Integration with AI Employee

This MCP server integrates with the Gold Tier workflow:

```
1. Task requires external action (send_email, post_linkedin, odoo create/pay)
2. Approval_Check_Skill flags the task (approval_needed: true)
3. Task moves to /Pending_Approval/
4. Human reviews and approves (approved: true) or rejects (status: rejected)
5. Approval_Handler_Skill calls the MCP tool
6. MCP_Action_Logger_Skill logs the result to Dashboard + System_Log
7. Task moves to /Done/
```

**CEO Briefing integration:** The `get_report` action is called during Phase 1 (Financial Audit) of the weekly CEO Briefing to pull live accounting data from Odoo. This is read-only and does not require approval.

**Error Recovery:** If an MCP tool call fails, the `Error_Recovery_Skill` classifies the error (transient vs permanent) and retries with exponential backoff (3 attempts) before escalating to the human.

## Testing

### Test Email

```bash
npm test
# or
node test_email.js
```

Sends a test email. Shows an Ethereal preview URL if using the test SMTP server.

### Test Odoo Connection

```bash
npm run test-odoo
# or
node test_odoo.js
```

Tests Odoo authentication and runs a sample `get_report` query.

### LinkedIn Auth Helper

```bash
npm run linkedin-auth
# or
node linkedin_auth.js
```

Helper script to obtain LinkedIn OAuth2 access token and Person URN.

## Demo Mode Summary

Everything works out of the box without credentials:

| Tool | Demo Behavior |
|------|--------------|
| `send_email` | Logs email to console (mock mode) |
| `post_linkedin` | Logs post content, returns simulated post ID |
| `check_email_config` | Reports mock mode status |
| `odoo_accounting` (create_invoice) | Returns simulated invoice with demo ID |
| `odoo_accounting` (log_payment) | Returns simulated payment with demo ID |
| `odoo_accounting` (get_report) | Returns sample data: $12,450 revenue, $8,326 expenses |

## Technical Details

- **Protocol:** Model Context Protocol (MCP) over stdio
- **Runtime:** Node.js 18+
- **Dependencies:** `@modelcontextprotocol/sdk`, `dotenv`, `nodemailer`
- **Odoo API:** JSON-RPC (native `fetch`, zero extra dependencies)
- **LinkedIn API:** UGC Posts API v2 (native `fetch`)
- **Server version:** 2.0.0

## Troubleshooting

### "Cannot find module" Error
```bash
npm install
```

### SMTP Connection Timeout
- Check firewall settings
- Verify SMTP host and port
- Try port 465 with `SMTP_SECURE=true`

### SMTP Authentication Failed
- For Gmail: Use App Password, not regular password
- Verify credentials in `.env`

### LinkedIn 401 Error
- Access token expired — regenerate via OAuth2 flow
- Run `node linkedin_auth.js` for guided setup

### LinkedIn 422 Error
- Check `LINKEDIN_PERSON_URN` format: must be `urn:li:person:<numeric_id>`
- Try `urn:li:member:<numeric_id>` if person URN doesn't work

### Odoo Authentication Failed
- Verify `ODOO_URL` has no trailing slash, `/odoo`, or `/web`
- Ensure `ODOO_API_KEY` is an API key (not login password)
- Check that the Accounting app is installed in your Odoo instance
- Test with: `npm run test-odoo`

### Odoo "Access Denied" on Create
- Your API key user needs Invoicing/Accounting permissions in Odoo
- Go to Settings > Users > your user > Access Rights

## Security Notes

- Never commit `.env` files with real credentials
- Use App Passwords for Gmail (not your main password)
- The `Approval_Check_Skill` gates all sensitive actions (email, LinkedIn, invoices, payments)
- Review tasks in `/Pending_Approval/` before authorizing
- `get_report` is read-only and safe to call without approval
- Odoo API keys can be revoked at any time from Settings > API Keys
