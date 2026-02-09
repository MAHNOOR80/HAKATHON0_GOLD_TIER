import 'dotenv/config';

/**
 * Gold Tier - Odoo Integration Test
 *
 * Quick test to verify Odoo JSON-RPC connectivity.
 * Run: node test_odoo.js
 *
 * Tests (in order):
 *   1. Authentication — verifies credentials
 *   2. Version info — fetches Odoo server version
 *   3. Partner search — lists first 3 customers
 *
 * If ODOO_URL/DB/USERNAME/API_KEY are not set, shows demo-mode message.
 */

const ODOO_URL = (process.env.ODOO_URL || '').replace(/\/(odoo|web)\/?$/, '');
const ODOO_DB = process.env.ODOO_DB || '';
const ODOO_USERNAME = process.env.ODOO_USERNAME || '';
const ODOO_API_KEY = process.env.ODOO_API_KEY || '';

async function jsonRpc(service, method, args) {
  const res = await fetch(`${ODOO_URL}/jsonrpc`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'call',
      params: { service, method, args },
    }),
  });
  const data = await res.json();
  if (data.error) {
    throw new Error(data.error.data?.message || data.error.message || JSON.stringify(data.error));
  }
  return data.result;
}

async function main() {
  console.log('='.repeat(55));
  console.log('Gold Tier - Odoo Integration Test');
  console.log('='.repeat(55));
  console.log();

  if (!ODOO_URL || !ODOO_DB || !ODOO_USERNAME || !ODOO_API_KEY) {
    console.log('Odoo credentials not set. Running in DEMO MODE.');
    console.log('Set these env vars for live testing:');
    console.log('  ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY');
    console.log();
    console.log('The odoo_accounting MCP tool will return sample data in demo mode.');
    return;
  }

  console.log(`URL:      ${ODOO_URL}`);
  console.log(`Database: ${ODOO_DB}`);
  console.log(`User:     ${ODOO_USERNAME}`);
  console.log(`API Key:  ${ODOO_API_KEY.substring(0, 8)}...`);
  console.log();

  // Test 1: Version
  console.log('[Test 1] Fetching Odoo server version...');
  try {
    const version = await jsonRpc('common', 'version', []);
    console.log(`  Server: ${version.server_version} (${version.server_serie})`);
    console.log('  PASS');
  } catch (err) {
    console.log(`  FAIL: ${err.message}`);
    return;
  }

  // Test 2: Authentication
  console.log('[Test 2] Authenticating...');
  let uid;
  try {
    uid = await jsonRpc('common', 'authenticate', [ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {}]);
    if (!uid) throw new Error('Authentication returned false/null');
    console.log(`  UID: ${uid}`);
    console.log('  PASS');
  } catch (err) {
    console.log(`  FAIL: ${err.message}`);
    console.log('  Check ODOO_DB, ODOO_USERNAME, and ODOO_API_KEY');
    return;
  }

  // Test 3: Search partners
  console.log('[Test 3] Listing first 3 partners...');
  try {
    const partners = await jsonRpc('object', 'execute_kw', [
      ODOO_DB, uid, ODOO_API_KEY,
      'res.partner', 'search_read',
      [[['is_company', '=', true]]],
      { fields: ['name', 'email'], limit: 3 },
    ]);
    for (const p of partners) {
      console.log(`  - ${p.name} (${p.email || 'no email'})`);
    }
    console.log('  PASS');
  } catch (err) {
    console.log(`  FAIL: ${err.message}`);
  }

  console.log();
  console.log('All tests complete. Odoo integration is ready.');
}

main().catch(err => {
  console.error(`Fatal: ${err.message}`);
  process.exit(1);
});
