#!/usr/bin/env node
/**
 * CodeSandbox Worker для RouterScan (аудит целей)
 * =================================================
 * Создаёт песочницу CodeSandbox (SDK @codesandbox/sdk), клонирует наш репозиторий,
 * запускает e2b_targets_audit.py на переданных целях и выводит результаты.
 *
 * Требуется: CSB_API_KEY (токен csb_... из https://codesandbox.io/t/api)
 * Установка SDK: npm install --no-save @codesandbox/sdk
 *
 * Usage:
 *   CSB_API_KEY=csb_... node csb_audit.js --targets "1.2.3.4,5.6.7.8" [--mode http|reach]
 *   CSB_API_KEY=csb_... node csb_audit.js --file targets.txt [--mode http]
 */

const { CodeSandbox } = require('@codesandbox/sdk');
const fs = require('fs');

const REPO = 'https://github.com/JoTalbot/scan.git';

function parseArgs() {
  const args = process.argv.slice(2);
  const out = { targets: [], mode: 'http' };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--targets' && args[i + 1]) {
      out.targets = args[i + 1].split(',').map((s) => s.trim()).filter(Boolean);
      i++;
    } else if (args[i] === '--file' && args[i + 1]) {
      out.targets = fs.readFileSync(args[i + 1], 'utf-8').split('\n').map((s) => s.trim()).filter(Boolean);
      i++;
    } else if (args[i] === '--mode' && args[i + 1]) {
      out.mode = args[i + 1];
      i++;
    }
  }
  return out;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const { targets, mode } = parseArgs();
  if (!targets.length) {
    console.error('Нет целей. Используйте --targets "ip1,ip2" или --file targets.txt');
    process.exit(1);
  }
  if (!process.env.CSB_API_KEY) {
    console.error('Нет CSB_API_KEY');
    process.exit(1);
  }

  console.log(`🚀 CodeSandbox: аудит ${targets.length} целей (mode=${mode})...`);
  const sdk = new CodeSandbox(process.env.CSB_API_KEY);
  const sandbox = await sdk.sandboxes.create();
  console.log(`  sandbox: ${sandbox.id}`);

  // ждём инициализацию песочницы (важно!)
  console.log('  ⏳ ожидание инициализации (20s)...');
  await sleep(20000);

  const session = await sandbox.connect();
  try {
    // 1. записываем цели (через base64 — безопасно от кавычек)
    const b64 = Buffer.from(targets.join('\n') + '\n').toString('base64');
    const w = await session.commands.run(`echo ${b64} | base64 -d > /tmp/targets.txt && wc -l /tmp/targets.txt`);
    console.log('  📤 targets.txt:', (w.output || '').trim().slice(-60) || 'ok');

    // 2. клонируем репо
    console.log('  ⚙️ Клонирую репозиторий...');
    const clone = await session.commands.run(`cd /tmp && git clone --depth 1 ${REPO} scan 2>&1 | tail -1`);
    console.log('  clone:', (clone.output || '').trim().slice(-80) || 'ok');

    // 3. запускаем аудит
    const cmd = `cd /tmp/scan && python3 e2b_targets_audit.py --targets-file /tmp/targets.txt --mode ${mode} 2>&1`;
    console.log(`  ⚙️ ${cmd}`);
    const out = await session.commands.run(cmd);
    console.log('=== РЕЗУЛЬТАТЫ ===');
    console.log(typeof out === 'string' ? out.slice(-4000) : JSON.stringify(out).slice(-4000));
    console.log('=== КОНЕЦ ===');
  } catch (e) {
    console.error('❌ Ошибка:', e.message ? e.message.slice(0, 300) : String(e).slice(0, 300));
    process.exit(1);
  }
  // песочница удаляется сама (hibernate), delete может не быть в SDK
  try { await sandbox.delete(); } catch (e) { /* ок */ }
}

main();
