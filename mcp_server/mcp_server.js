/**
 * Gold Tier AI Employee - MCP Server
 *
 * This server exposes tools via the Model Context Protocol (MCP),
 * allowing Claude Code to perform external actions like sending emails,
 * posting to LinkedIn, and managing Odoo accounting.
 *
 * MCP servers communicate over stdio (standard input/output),
 * which is how Claude Code connects to them.
 *
 * Tools provided:
 *   - send_email: Send an email via SMTP
 *   - post_linkedin: Post content to LinkedIn
 *   - check_email_config: Verify SMTP connection
 *   - odoo_accounting: Create invoices, log payments, get reports via Odoo ERP
 *
 * Usage:
 *   node mcp_server.js
 *
 * Configuration:
 *   Set environment variables for SMTP / LinkedIn / Odoo (see .env.example)
 */

import 'dotenv/config';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import nodemailer from 'nodemailer';

// =============================================================================
// CONFIGURATION
// =============================================================================

// SMTP Configuration - Set these via environment variables for security
const SMTP_CONFIG = {
  host: process.env.SMTP_HOST || 'smtp.gmail.com',
  port: parseInt(process.env.SMTP_PORT || '587'),
  secure: process.env.SMTP_SECURE === 'true', // true for 465, false for other ports
  auth: {
    user: process.env.SMTP_USER || '',
    pass: process.env.SMTP_PASS || '',
  },
};

// Default sender email (can be overridden per request)
const DEFAULT_FROM = process.env.SMTP_FROM || 'ai-employee@example.com';

// Enable test mode (logs emails instead of sending)
const TEST_MODE = process.env.TEST_MODE === 'true' || !SMTP_CONFIG.auth.user;

// =============================================================================
// LINKEDIN CONFIGURATION
// =============================================================================

// LinkedIn API credentials - get these from https://developer.linkedin.com/
// 1. Create an app at LinkedIn Developer Portal
// 2. Add "Share on LinkedIn" product
// 3. Generate an OAuth2 access token
const LINKEDIN_CONFIG = {
  accessToken: process.env.LINKEDIN_ACCESS_TOKEN || '',
  personUrn: process.env.LINKEDIN_PERSON_URN || '', // format: "urn:li:person:XXXXXXXX"
};

// LinkedIn test mode if no credentials
const LINKEDIN_TEST_MODE = !LINKEDIN_CONFIG.accessToken || !LINKEDIN_CONFIG.personUrn;

// =============================================================================
// ODOO CONFIGURATION (Gold Tier)
// =============================================================================

// Odoo ERP connection — uses JSON-RPC (native fetch, zero extra deps)
// Setup:
//   1. Create free Odoo instance at https://www.odoo.com/trial
//   2. Enable Accounting app
//   3. Go to Settings > Users > your user > API Keys > New Key
//   4. Set the env vars below
const ODOO_CONFIG = {
  // Strip trailing /odoo, /web, etc. to get the base URL for JSON-RPC
  url: (process.env.ODOO_URL || '').replace(/\/(odoo|web)\/?$/, ''),
  db: process.env.ODOO_DB || '',
  username: process.env.ODOO_USERNAME || '',
  apiKey: process.env.ODOO_API_KEY || '',
};

// Odoo test mode if any credential is missing
const ODOO_TEST_MODE = !ODOO_CONFIG.url || !ODOO_CONFIG.db || !ODOO_CONFIG.username || !ODOO_CONFIG.apiKey;

// Cached Odoo UID (set after first successful authenticate call)
let odooUid = null;


// =============================================================================
// EMAIL TRANSPORT SETUP
// =============================================================================

let transporter = null;

/**
 * Initialize the email transporter.
 * Always uses configured SMTP settings — no Ethereal fallback.
 */
async function initializeTransporter() {
  if (!SMTP_CONFIG.auth.user) {
    console.error('[MCP] WARNING: No SMTP credentials configured (SMTP_USER is empty)');
    console.error('[MCP] Email will run in mock mode — set SMTP_USER and SMTP_PASS in .env');
    transporter = null;
    return;
  }

  transporter = nodemailer.createTransport(SMTP_CONFIG);
  console.error(`[MCP] SMTP configured: ${SMTP_CONFIG.host}:${SMTP_CONFIG.port} as ${SMTP_CONFIG.auth.user}`);
}


// =============================================================================
// ODOO JSON-RPC HELPERS (Gold Tier)
// =============================================================================

/**
 * Make a JSON-RPC call to the Odoo server.
 *
 * @param {string} service  - 'common' or 'object'
 * @param {string} method   - RPC method name
 * @param {Array}  args     - Positional arguments
 * @returns {*} The JSON-RPC result
 */
async function odooJsonRpc(service, method, args) {
  const endpoint = `${ODOO_CONFIG.url}/jsonrpc`;

  const payload = {
    jsonrpc: '2.0',
    id: Date.now(),
    method: 'call',
    params: { service, method, args },
  };

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Odoo HTTP ${response.status}: ${response.statusText}`);
  }

  const data = await response.json();

  if (data.error) {
    const msg = data.error.data?.message || data.error.message || JSON.stringify(data.error);
    throw new Error(`Odoo RPC error: ${msg}`);
  }

  return data.result;
}


/**
 * Authenticate with Odoo and cache the UID.
 * Uses API key as the password (Odoo treats API keys as passwords in XML/JSON-RPC).
 *
 * @returns {number} The authenticated user ID
 */
async function odooAuthenticate() {
  if (odooUid) return odooUid;

  const uid = await odooJsonRpc('common', 'authenticate', [
    ODOO_CONFIG.db,
    ODOO_CONFIG.username,
    ODOO_CONFIG.apiKey,
    {},
  ]);

  if (!uid) {
    throw new Error('Odoo authentication failed — check ODOO_URL, ODOO_DB, ODOO_USERNAME, and ODOO_API_KEY');
  }

  odooUid = uid;
  console.error(`[MCP] Odoo authenticated as UID ${uid}`);
  return uid;
}


/**
 * Execute a model method on Odoo via JSON-RPC.
 *
 * @param {string} model   - Odoo model name (e.g. 'account.move')
 * @param {string} method  - Model method (e.g. 'create', 'search_read')
 * @param {Array}  args    - Positional args (e.g. domain, vals)
 * @param {Object} kwargs  - Keyword args (e.g. fields, limit)
 * @returns {*} Method result
 */
async function odooExecute(model, method, args = [], kwargs = {}) {
  const uid = await odooAuthenticate();

  return odooJsonRpc('object', 'execute_kw', [
    ODOO_CONFIG.db,
    uid,
    ODOO_CONFIG.apiKey,
    model,
    method,
    args,
    kwargs,
  ]);
}


/**
 * Look up an Odoo partner (customer/vendor) by name.
 * Creates one if not found.
 *
 * @param {string} name - Customer/vendor name
 * @returns {number} partner ID
 */
async function odooFindOrCreatePartner(name) {
  // Search first
  const ids = await odooExecute('res.partner', 'search', [
    [['name', 'ilike', name]],
  ], { limit: 1 });

  if (ids && ids.length > 0) return ids[0];

  // Create if not found
  const newId = await odooExecute('res.partner', 'create', [
    { name: name },
  ]);

  console.error(`[MCP] Created new Odoo partner: ${name} (ID: ${newId})`);
  return newId;
}


// =============================================================================
// TOOL DEFINITIONS
// =============================================================================

/**
 * List of tools exposed by this MCP server.
 * Each tool has a name, description, and input schema (JSON Schema format).
 */
const TOOLS = [
  {
    name: 'send_email',
    description: `Send an email via SMTP. Requires approval for sensitive communications.

Use this tool to send emails on behalf of the AI Employee.
The email will be sent from the configured SMTP account.

IMPORTANT: This action should be flagged as approval_needed in task files
before execution, as per the Approval_Check_Skill.`,
    inputSchema: {
      type: 'object',
      properties: {
        to: {
          type: 'string',
          description: 'Recipient email address (e.g., "user@example.com")',
        },
        subject: {
          type: 'string',
          description: 'Email subject line',
        },
        body: {
          type: 'string',
          description: 'Email body content (plain text or HTML)',
        },
        from: {
          type: 'string',
          description: 'Sender email address (optional, uses default if not provided)',
        },
        html: {
          type: 'boolean',
          description: 'If true, body is treated as HTML. Default: false (plain text)',
        },
      },
      required: ['to', 'subject', 'body'],
    },
  },
  {
    name: 'post_linkedin',
    description: `Post content to LinkedIn on behalf of the user.

Use this tool to publish professional posts to LinkedIn.
Supports text posts with optional visibility settings.

IMPORTANT: This action ALWAYS requires human approval via the
Approval_Check_Skill before execution.

Setup:
  Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN environment variables.
  Without credentials, runs in test/demo mode (logs post, does not publish).`,
    inputSchema: {
      type: 'object',
      properties: {
        content: {
          type: 'string',
          description: 'The post content/text to publish on LinkedIn',
        },
        visibility: {
          type: 'string',
          description: 'Post visibility: "PUBLIC" or "CONNECTIONS". Default: "PUBLIC"',
        },
      },
      required: ['content'],
    },
  },
  {
    name: 'check_email_config',
    description: 'Check if email is properly configured and test the connection.',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
  },
  {
    name: 'odoo_accounting',
    description: `Manage accounting in Odoo ERP (Gold Tier).

Supports three actions:
  - "create_invoice": Create a new customer invoice (draft)
  - "log_payment": Record an incoming or outgoing payment
  - "get_report": Retrieve a financial summary (revenue/expense)

IMPORTANT: create_invoice and log_payment require human approval via
Approval_Check_Skill (financial actions). get_report is read-only.

Setup:
  Set ODOO_URL, ODOO_DB, ODOO_USERNAME, and ODOO_API_KEY in .env.
  Without credentials, runs in test/demo mode.
  Get a free test DB at https://www.odoo.com/trial (enable Accounting app).`,
    inputSchema: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          description: 'The accounting action: "create_invoice", "log_payment", or "get_report"',
          enum: ['create_invoice', 'log_payment', 'get_report'],
        },
        customer: {
          type: 'string',
          description: '(create_invoice / log_payment) Customer or vendor name',
        },
        amount: {
          type: 'number',
          description: '(create_invoice / log_payment) Amount in company currency',
        },
        description: {
          type: 'string',
          description: '(create_invoice) Line item description. (log_payment) Payment memo.',
        },
        payment_type: {
          type: 'string',
          description: '(log_payment) "inbound" for received money, "outbound" for sent money. Default: "inbound"',
        },
        report_type: {
          type: 'string',
          description: '(get_report) Report type: "revenue_weekly", "revenue_monthly", "expenses_weekly", "expenses_monthly", or "summary". Default: "summary"',
        },
        date_from: {
          type: 'string',
          description: '(get_report) Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)',
        },
        date_to: {
          type: 'string',
          description: '(get_report) End date in YYYY-MM-DD format (optional, defaults to today)',
        },
      },
      required: ['action'],
    },
  },
];


// =============================================================================
// TOOL HANDLERS
// =============================================================================

/**
 * Send an email using the configured SMTP transport.
 *
 * @param {Object} params - Email parameters
 * @param {string} params.to - Recipient email address
 * @param {string} params.subject - Email subject
 * @param {string} params.body - Email body
 * @param {string} [params.from] - Sender email (optional)
 * @param {boolean} [params.html] - Treat body as HTML
 * @returns {Object} Result with success status and details
 */
async function handleSendEmail(params) {
  const { to, subject, body, from = DEFAULT_FROM, html = false } = params;

  // Validate required parameters
  if (!to || !subject || !body) {
    return {
      success: false,
      error: 'Missing required parameters: to, subject, and body are required',
    };
  }

  // Validate email format (basic check)
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(to)) {
    return {
      success: false,
      error: `Invalid email address format: ${to}`,
    };
  }

  // Build the email message
  const mailOptions = {
    from: from,
    to: to,
    subject: subject,
    [html ? 'html' : 'text']: body,
  };

  // If no transporter (mock mode), just log the email
  if (!transporter) {
    console.error('[MCP] Mock mode - Email would be sent:');
    console.error(JSON.stringify(mailOptions, null, 2));
    return {
      success: true,
      mode: 'mock',
      message: 'Email logged (mock mode - no SMTP configured)',
      details: mailOptions,
    };
  }

  try {
    // Send the email
    const info = await transporter.sendMail(mailOptions);

    console.error(`[MCP] Email sent successfully to ${to} (messageId: ${info.messageId})`);
    return {
      success: true,
      messageId: info.messageId,
      to: to,
      subject: subject,
    };

  } catch (error) {
    console.error(`[MCP] Email send failed: ${error.message}`);
    return {
      success: false,
      error: error.message,
      code: error.code,
    };
  }
}


/**
 * Post content to LinkedIn using the official REST API v2 (/rest/posts).
 *
 * API docs: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
 *
 * @param {Object} params - Post parameters
 * @param {string} params.content - The text content to post
 * @param {string} [params.visibility] - "PUBLIC" or "CONNECTIONS"
 * @returns {Object} Result with success status and details
 */
async function handlePostLinkedin(params) {
  const { content, visibility = 'PUBLIC' } = params;

  // Validate content
  if (!content || content.trim().length === 0) {
    return {
      success: false,
      error: 'Missing required parameter: content cannot be empty',
    };
  }

  // LinkedIn has a ~3000 character limit for posts
  if (content.length > 3000) {
    return {
      success: false,
      error: `Post content too long: ${content.length} characters (max 3000)`,
    };
  }

  // Validate visibility
  const validVisibility = ['PUBLIC', 'CONNECTIONS'];
  const vis = visibility.toUpperCase();
  if (!validVisibility.includes(vis)) {
    return {
      success: false,
      error: `Invalid visibility "${visibility}". Must be PUBLIC or CONNECTIONS`,
    };
  }

  // ---- TEST/DEMO MODE ----
  if (LINKEDIN_TEST_MODE) {
    console.error('[MCP] LinkedIn test mode - Post would be published:');
    console.error(`[MCP]   Content: ${content.substring(0, 100)}...`);
    console.error(`[MCP]   Visibility: ${vis}`);
    console.error(`[MCP]   Length: ${content.length} chars`);

    const demoPostId = `demo-${Date.now()}`;
    return {
      success: true,
      mode: 'test',
      message: 'LinkedIn post logged (test mode — no API credentials configured)',
      postId: demoPostId,
      postUrl: `https://www.linkedin.com/feed/update/${demoPostId}`,
      content: content.substring(0, 200) + (content.length > 200 ? '...' : ''),
      visibility: vis,
      characterCount: content.length,
      note: 'Run "node linkedin_auth.js" to get LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN',
    };
  }

  // ---- LIVE MODE — LinkedIn UGC Posts API (/v2/ugcPosts) ----
  // "Share on LinkedIn" product provides w_member_social scope + UGC API access.
  // The newer /rest/posts endpoint requires Community Management API (separate product).
  try {
    const postBody = {
      author: LINKEDIN_CONFIG.personUrn,
      lifecycleState: 'PUBLISHED',
      specificContent: {
        'com.linkedin.ugc.ShareContent': {
          shareCommentary: {
            text: content,
          },
          shareMediaCategory: 'NONE',
        },
      },
      visibility: {
        'com.linkedin.ugc.MemberNetworkVisibility': vis,
      },
    };

    const response = await fetch('https://api.linkedin.com/v2/ugcPosts', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${LINKEDIN_CONFIG.accessToken}`,
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
      },
      body: JSON.stringify(postBody),
    });

    if (response.status === 201 || response.ok) {
      const data = await response.json();
      const postId = data.id || response.headers.get('x-restli-id') || '';

      console.error(`[MCP] LinkedIn post published successfully: ${postId}`);
      return {
        success: true,
        mode: 'live',
        postId: postId,
        postUrl: postId
          ? `https://www.linkedin.com/feed/update/${postId}`
          : 'https://www.linkedin.com/feed/',
        visibility: vis,
        characterCount: content.length,
        message: `Post published to LinkedIn (${vis})`,
      };
    }

    // Error response
    const errorBody = await response.text();
    console.error(`[MCP] LinkedIn API error: ${response.status} - ${errorBody}`);

    let hint = '';
    if (response.status === 401) {
      hint = 'Access token expired or invalid. Run "node linkedin_auth.js" to get a new token.';
    } else if (response.status === 403) {
      hint = 'Missing permissions. Ensure your LinkedIn app has the "w_member_social" scope.';
    } else if (response.status === 422) {
      hint = 'Invalid post data. Check LINKEDIN_PERSON_URN format (should be urn:li:member:<numeric_id>).';
    }

    return {
      success: false,
      error: `LinkedIn API error: ${response.status}`,
      details: errorBody,
      hint: hint || undefined,
    };

  } catch (error) {
    console.error(`[MCP] LinkedIn post failed: ${error.message}`);
    return {
      success: false,
      error: error.message,
    };
  }
}


/**
 * Check email configuration and connection status.
 *
 * @returns {Object} Configuration status and details
 */
async function handleCheckEmailConfig() {
  const config = {
    testMode: TEST_MODE,
    smtpHost: SMTP_CONFIG.host,
    smtpPort: SMTP_CONFIG.port,
    hasCredentials: !!SMTP_CONFIG.auth.user,
    defaultFrom: DEFAULT_FROM,
  };

  // Test connection if transporter exists
  if (transporter) {
    try {
      await transporter.verify();
      config.connectionStatus = 'connected';
      config.message = 'SMTP connection verified successfully';
    } catch (error) {
      config.connectionStatus = 'error';
      config.message = `Connection failed: ${error.message}`;
    }
  } else {
    config.connectionStatus = 'mock';
    config.message = 'Running in mock mode (no SMTP configured)';
  }

  return config;
}


// =============================================================================
// ODOO ACCOUNTING HANDLER (Gold Tier)
// =============================================================================

/**
 * Handle Odoo accounting actions: create_invoice, log_payment, get_report.
 *
 * @param {Object} params - Action parameters
 * @returns {Object} Result with success status and details
 */
async function handleOdooAccounting(params) {
  const { action } = params;

  if (!action) {
    return { success: false, error: 'Missing required parameter: action' };
  }

  // ---- TEST/DEMO MODE ----
  if (ODOO_TEST_MODE) {
    return handleOdooDemo(params);
  }

  // ---- LIVE MODE ----
  try {
    switch (action) {
      case 'create_invoice':
        return await odooCreateInvoice(params);
      case 'log_payment':
        return await odooLogPayment(params);
      case 'get_report':
        return await odooGetReport(params);
      default:
        return {
          success: false,
          error: `Unknown action "${action}". Use: create_invoice, log_payment, or get_report`,
        };
    }
  } catch (error) {
    console.error(`[MCP] Odoo ${action} failed: ${error.message}`);
    return {
      success: false,
      error: error.message,
      action: action,
      hint: 'Check ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY in .env',
    };
  }
}


/**
 * Demo/test handler when Odoo credentials are not configured.
 */
function handleOdooDemo(params) {
  const { action, customer, amount, description, payment_type, report_type } = params;

  console.error(`[MCP] Odoo test mode — action: ${action}`);

  switch (action) {
    case 'create_invoice':
      if (!customer || !amount) {
        return { success: false, error: 'create_invoice requires: customer, amount' };
      }
      return {
        success: true,
        mode: 'test',
        action: 'create_invoice',
        message: 'Invoice logged (test mode — no Odoo credentials configured)',
        invoice: {
          id: `demo-inv-${Date.now()}`,
          customer: customer,
          amount: amount,
          description: description || 'Services rendered',
          state: 'draft',
          currency: 'USD',
        },
        note: 'Set ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY for live mode',
      };

    case 'log_payment':
      if (!customer || !amount) {
        return { success: false, error: 'log_payment requires: customer, amount' };
      }
      return {
        success: true,
        mode: 'test',
        action: 'log_payment',
        message: 'Payment logged (test mode — no Odoo credentials configured)',
        payment: {
          id: `demo-pay-${Date.now()}`,
          customer: customer,
          amount: amount,
          type: payment_type || 'inbound',
          memo: description || '',
          state: 'draft',
        },
        note: 'Set ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY for live mode',
      };

    case 'get_report': {
      const type = report_type || 'summary';
      return {
        success: true,
        mode: 'test',
        action: 'get_report',
        message: `Report generated (test mode — sample data for "${type}")`,
        report: {
          type: type,
          period: 'last 30 days (demo)',
          total_revenue: 12450.00,
          total_expenses: 8326.49,
          net_profit: 4123.51,
          invoice_count: 5,
          payment_count: 3,
          top_customers: ['Acme Corp', 'Widget Co', 'Beta Inc'],
        },
        note: 'Set ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY for live mode',
      };
    }

    default:
      return {
        success: false,
        error: `Unknown action "${action}". Use: create_invoice, log_payment, or get_report`,
      };
  }
}


/**
 * Create a draft customer invoice in Odoo.
 *
 * Uses model: account.move (type: out_invoice)
 */
async function odooCreateInvoice(params) {
  const { customer, amount, description = 'Services rendered' } = params;

  if (!customer || amount === undefined || amount === null) {
    return { success: false, error: 'create_invoice requires: customer, amount' };
  }

  if (typeof amount !== 'number' || amount <= 0) {
    return { success: false, error: 'amount must be a positive number' };
  }

  // Find or create the customer partner
  const partnerId = await odooFindOrCreatePartner(customer);

  // Create the invoice with one line item
  const invoiceId = await odooExecute('account.move', 'create', [{
    move_type: 'out_invoice',
    partner_id: partnerId,
    invoice_line_ids: [
      [0, 0, {
        name: description,
        quantity: 1,
        price_unit: amount,
      }],
    ],
  }]);

  // Read back the created invoice for confirmation
  const invoices = await odooExecute('account.move', 'read', [[invoiceId]], {
    fields: ['name', 'state', 'amount_total', 'currency_id', 'invoice_date', 'partner_id'],
  });

  const inv = invoices[0];
  console.error(`[MCP] Odoo invoice created: ${inv.name} (ID: ${invoiceId})`);

  return {
    success: true,
    mode: 'live',
    action: 'create_invoice',
    invoice: {
      id: invoiceId,
      number: inv.name,
      customer: inv.partner_id?.[1] || customer,
      amount: inv.amount_total,
      currency: inv.currency_id?.[1] || 'USD',
      date: inv.invoice_date || 'auto',
      state: inv.state,
      description: description,
    },
    message: `Invoice ${inv.name} created for ${customer} — $${inv.amount_total} (${inv.state})`,
  };
}


/**
 * Record a payment in Odoo.
 *
 * Uses model: account.payment
 */
async function odooLogPayment(params) {
  const {
    customer,
    amount,
    description = '',
    payment_type = 'inbound',
  } = params;

  if (!customer || amount === undefined || amount === null) {
    return { success: false, error: 'log_payment requires: customer, amount' };
  }

  if (typeof amount !== 'number' || amount <= 0) {
    return { success: false, error: 'amount must be a positive number' };
  }

  const validTypes = ['inbound', 'outbound'];
  if (!validTypes.includes(payment_type)) {
    return { success: false, error: `payment_type must be "inbound" or "outbound", got "${payment_type}"` };
  }

  const partnerId = await odooFindOrCreatePartner(customer);

  // Determine partner_type based on payment direction
  const partnerType = payment_type === 'inbound' ? 'customer' : 'supplier';

  // Find the first bank journal (type = 'bank')
  const journalIds = await odooExecute('account.journal', 'search', [
    [['type', '=', 'bank']],
  ], { limit: 1 });

  const journalId = journalIds && journalIds.length > 0 ? journalIds[0] : false;

  const paymentVals = {
    payment_type: payment_type,
    partner_type: partnerType,
    partner_id: partnerId,
    amount: amount,
    // Note: 'ref' field removed — not available in this Odoo version (saas~19.1)
  };

  if (journalId) {
    paymentVals.journal_id = journalId;
  }

  const paymentId = await odooExecute('account.payment', 'create', [paymentVals]);

  // Read back the payment
  const payments = await odooExecute('account.payment', 'read', [[paymentId]], {
    fields: ['name', 'state', 'amount', 'payment_type', 'partner_id'],
  });

  const pay = payments[0];
  console.error(`[MCP] Odoo payment recorded: ${pay.name} (ID: ${paymentId})`);

  return {
    success: true,
    mode: 'live',
    action: 'log_payment',
    payment: {
      id: paymentId,
      name: pay.name,
      customer: pay.partner_id?.[1] || customer,
      amount: pay.amount,
      type: pay.payment_type,
      memo: description || '',
      state: pay.state,
    },
    message: `Payment ${pay.name} recorded — ${payment_type} $${pay.amount} for ${customer}`,
  };
}


/**
 * Retrieve a financial report/summary from Odoo.
 *
 * Reads account.move records and aggregates totals.
 */
async function odooGetReport(params) {
  const { report_type = 'summary', date_from, date_to } = params;

  // Calculate date range
  const now = new Date();
  const defaultFrom = new Date(now);

  if (report_type.includes('weekly')) {
    defaultFrom.setDate(now.getDate() - 7);
  } else {
    defaultFrom.setDate(now.getDate() - 30);
  }

  const from = date_from || defaultFrom.toISOString().split('T')[0];
  const to = date_to || now.toISOString().split('T')[0];

  // Build domain filter based on report type
  let moveType;
  if (report_type.startsWith('revenue')) {
    moveType = 'out_invoice';
  } else if (report_type.startsWith('expenses')) {
    moveType = 'in_invoice';
  } else {
    moveType = null; // summary — fetch both
  }

  const baseDomain = [
    ['invoice_date', '>=', from],
    ['invoice_date', '<=', to],
    ['state', '!=', 'cancel'],
  ];

  // Fetch invoices (revenue)
  const revenueDomain = [...baseDomain, ['move_type', '=', 'out_invoice']];
  const invoices = moveType !== 'in_invoice'
    ? await odooExecute('account.move', 'search_read', [revenueDomain], {
        fields: ['name', 'partner_id', 'amount_total', 'state', 'invoice_date'],
        order: 'invoice_date desc',
        limit: 100,
      })
    : [];

  // Fetch bills (expenses)
  const expenseDomain = [...baseDomain, ['move_type', '=', 'in_invoice']];
  const bills = moveType !== 'out_invoice'
    ? await odooExecute('account.move', 'search_read', [expenseDomain], {
        fields: ['name', 'partner_id', 'amount_total', 'state', 'invoice_date'],
        order: 'invoice_date desc',
        limit: 100,
      })
    : [];

  // Fetch payments
  const paymentDomain = [
    ['date', '>=', from],
    ['date', '<=', to],
    ['state', '!=', 'cancelled'],
  ];
  const payments = await odooExecute('account.payment', 'search_read', [paymentDomain], {
    fields: ['name', 'partner_id', 'amount', 'payment_type', 'state', 'date'],
    order: 'date desc',
    limit: 100,
  });

  // Aggregate
  const totalRevenue = invoices.reduce((sum, inv) => sum + (inv.amount_total || 0), 0);
  const totalExpenses = bills.reduce((sum, bill) => sum + (bill.amount_total || 0), 0);

  // Top customers by revenue
  const customerMap = {};
  for (const inv of invoices) {
    const name = inv.partner_id?.[1] || 'Unknown';
    customerMap[name] = (customerMap[name] || 0) + (inv.amount_total || 0);
  }
  const topCustomers = Object.entries(customerMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, total]) => ({ name, total }));

  console.error(`[MCP] Odoo report: ${report_type} (${from} to ${to})`);

  return {
    success: true,
    mode: 'live',
    action: 'get_report',
    report: {
      type: report_type,
      period: { from, to },
      total_revenue: Math.round(totalRevenue * 100) / 100,
      total_expenses: Math.round(totalExpenses * 100) / 100,
      net_profit: Math.round((totalRevenue - totalExpenses) * 100) / 100,
      invoice_count: invoices.length,
      bill_count: bills.length,
      payment_count: payments.length,
      top_customers: topCustomers,
      recent_invoices: invoices.slice(0, 5).map(inv => ({
        number: inv.name,
        customer: inv.partner_id?.[1],
        amount: inv.amount_total,
        date: inv.invoice_date,
        state: inv.state,
      })),
      recent_bills: bills.slice(0, 5).map(bill => ({
        number: bill.name,
        vendor: bill.partner_id?.[1],
        amount: bill.amount_total,
        date: bill.invoice_date,
        state: bill.state,
      })),
    },
    message: `${report_type} report: Revenue $${totalRevenue.toFixed(2)}, Expenses $${totalExpenses.toFixed(2)}, Net $${(totalRevenue - totalExpenses).toFixed(2)} (${from} to ${to})`,
  };
}


// =============================================================================
// MCP SERVER SETUP
// =============================================================================

/**
 * Create and configure the MCP server.
 */
function createServer() {
  const server = new Server(
    {
      name: 'gold-tier-mcp-server',
      version: '2.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // Handler for listing available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: TOOLS,
    };
  });

  // Handler for executing tools
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    console.error(`[MCP] Tool called: ${name}`);
    console.error(`[MCP] Arguments: ${JSON.stringify(args)}`);

    try {
      let result;

      switch (name) {
        case 'send_email':
          result = await handleSendEmail(args);
          break;

        case 'post_linkedin':
          result = await handlePostLinkedin(args);
          break;

        case 'check_email_config':
          result = await handleCheckEmailConfig();
          break;

        case 'odoo_accounting':
          result = await handleOdooAccounting(args);
          break;

        default:
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify({ error: `Unknown tool: ${name}` }),
              },
            ],
            isError: true,
          };
      }

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
      };

    } catch (error) {
      console.error(`[MCP] Error executing tool ${name}: ${error.message}`);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({ error: error.message }),
          },
        ],
        isError: true,
      };
    }
  });

  return server;
}


// =============================================================================
// MAIN ENTRY POINT
// =============================================================================

async function main() {
  console.error('='.repeat(55));
  console.error('Gold Tier AI Employee - MCP Server');
  console.error('='.repeat(55));

  // Initialize email transporter
  await initializeTransporter();

  // Log Odoo config status
  if (ODOO_TEST_MODE) {
    console.error('[MCP] Odoo: TEST MODE (set ODOO_URL/DB/USERNAME/API_KEY for live)');
  } else {
    console.error(`[MCP] Odoo: ${ODOO_CONFIG.url} (db: ${ODOO_CONFIG.db})`);
  }

  // Create the MCP server
  const server = createServer();

  // Connect via stdio transport (how Claude Code communicates)
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('[MCP] Server running on stdio');
  console.error('[MCP] Available tools: send_email, post_linkedin, check_email_config, odoo_accounting');
  console.error('[MCP] Waiting for requests...');
}

// Run the server
main().catch((error) => {
  console.error(`[MCP] Fatal error: ${error.message}`);
  process.exit(1);
});
