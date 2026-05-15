#!/usr/bin/env node
const https = require('https');

const COOKIE = '1778786005|QOXVbosBbDaa';
const DOMAIN = 'paolamaccioni.com';

// Netlify nameservers
const NS = [
  'dns1.netlify.com',
  'dns2.netlify.com',
  'dns3.netlify.com',
  'dns4.netlify.com'
];

function request(method, path, body = null) {
  return new Promise((resolve, reject) => {
    const opts = {
      hostname: 'www.wix.com',
      port: 443,
      path,
      method,
      headers: {
        'Cookie': `nes_session=${COOKIE}`,
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0'
      }
    };
    if (body) opts.headers['Content-Length'] = Buffer.byteLength(body);

    const req = https.request(opts, (res) => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, data: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, data });
        }
      });
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

async function main() {
  console.log('🔄 Fetching domain info...');

  // Get domain ID
  const domains = await request('GET', '/api/v1/contacts/domains');
  if (domains.status !== 200) {
    console.error('❌ Failed to fetch domains:', domains);
    process.exit(1);
  }

  const domain = domains.data.domains?.find(d => d.name === DOMAIN);
  if (!domain) {
    console.error(`❌ Domain ${DOMAIN} not found`);
    process.exit(1);
  }

  console.log(`✓ Found domain: ${domain.name} (id: ${domain.id})`);

  // Update nameservers
  console.log('🔄 Updating nameservers...');
  const payload = JSON.stringify({
    nameServers: NS
  });

  const update = await request('PATCH', `/api/v1/domains/${domain.id}/nameservers`, payload);

  if (update.status === 200) {
    console.log('✅ Nameservers updated!');
    console.log('Nameservers set to:');
    NS.forEach(ns => console.log(`   ${ns}`));
    console.log('\n⏱️  Propagation may take 24-48 hours (usually faster).');
  } else {
    console.error('❌ Failed to update:', update);
    process.exit(1);
  }
}

main().catch(e => { console.error('❌ Error:', e); process.exit(1); });
