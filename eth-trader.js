// ETH 合约交易中枢
// 用法: node eth-trader <命令> [参数]

const https = require('https');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// ============================================================
// 配置
// ============================================================
const CONFIG = {
  okx: {
    apiKey: 'f79530be-4cb6-4f06-a76b-c091e9c8aa81',
    secretKey: 'CB988B82A01D5F8C1BC3598228AFB20F',
    passphrase: 'Wang20040508@',
    base: 'www.okx.com'
  },
  capital: 10,       // 总本金
  riskPerTrade: 0.10, // 单笔最大亏损比例
  leverage: 125,     // 默认杠杆
  tradeLog: path.join(__dirname, 'trades.json')
};

// ============================================================
// 工具函数
// ============================================================
function httpGet(url, cb) {
  https.get(url, res => {
    let d = '';
    res.on('data', c => d += c);
    res.on('end', () => { try { cb(null, JSON.parse(d)); } catch(e) { cb(e); } });
  }).on('error', e => cb(e));
}

function okxReq(method, path, body, cb) {
  const ts = new Date().toISOString();
  const signStr = ts + method + path + (body || '');
  const sig = crypto.createHmac('sha256', CONFIG.okx.secretKey).update(signStr).digest('base64');
  const req = https.request({
    hostname: CONFIG.okx.base, port: 443, path, method,
    headers: {
      'OK-ACCESS-KEY': CONFIG.okx.apiKey, 'OK-ACCESS-SIGN': sig,
      'OK-ACCESS-TIMESTAMP': ts, 'OK-ACCESS-PASSPHRASE': CONFIG.okx.passphrase,
      'Content-Type': 'application/json'
    }
  }, res => {
    let d = '';
    res.on('data', c => d += c);
    res.on('end', () => { try { cb(null, JSON.parse(d)); } catch(e) { cb(e); } });
  });
  req.on('error', e => cb(e));
  if (body) req.write(body);
  req.end();
}

function round(n, d=2) { return Math.round(n * Math.pow(10,d)) / Math.pow(10,d); }

// ============================================================
// 1. 实时行情
// ============================================================
function marketSnapshot() {
  let ethPrice, fundingRate, openInterest, fearGreed;
  let done = 0;
  function check() {
    done++;
    if (done < 4) return;
    console.log('');
    console.log('═══════════════════════════════════════');
    console.log('  ETH 合约实时行情');
    console.log('═══════════════════════════════════════');
    console.log('  价格     : $' + ethPrice);
    console.log('  资金费率 : ' + fundingRate + '%');
    console.log('  持仓量   : ' + openInterest + 'M 张');
    console.log('  恐惧贪婪 : ' + fearGreed + '/100');
    console.log('═══════════════════════════════════════');
    showPositionCalc(ethPrice);
  }

  httpGet('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd&include_24hr_change=true', (err, d) => {
    ethPrice = d ? d.ethereum.usd : '---'; check();
  });
  httpGet('https://www.okx.com/api/v5/public/funding-rate?instId=ETH-USDT-SWAP', (err, d) => {
    fundingRate = d ? round(parseFloat(d.data[0].fundingRate)*100, 5) : '---'; check();
  });
  httpGet('https://www.okx.com/api/v5/public/open-interest?instId=ETH-USDT-SWAP', (err, d) => {
    openInterest = d ? round(parseFloat(d.data[0].oi)/1e6, 1) : '---'; check();
  });
  httpGet('https://api.alternative.me/fng/?limit=1', (err, d) => {
    fearGreed = d ? d.data[0].value : '---'; check();
  });
}

// ============================================================
// 2. 仓位计算器
// ============================================================
function showPositionCalc(price) {
  const p = price || 2100;
  console.log('');
  console.log('═══════════════════════════════════════');
  console.log('  仓位计算器 (本金 $' + CONFIG.capital + ')');
  console.log('═══════════════════════════════════════');

  const margins = [0.15, 0.20, 0.25, 0.30];
  const leverages = [50, 75, 100, 125, 150];

  for (let mPct of margins) {
    const margin = round(CONFIG.capital * mPct, 1);
    for (let lev of leverages) {
      const pos = margin * lev;
      const stopAmt = round(CONFIG.capital * CONFIG.riskPerTrade, 1);
      const stopPts = round(stopAmt / pos * p, 1);
      const tpPts = 25;
      const profit = round(tpPts / p * pos, 1);
      const rr = round(profit / stopAmt, 1);
      const mark = stopPts >= 5 ? '✅' : stopPts >= 3 ? '⚠️' : '❌';
      console.log(`  ${mark} 保证金${margin}U | ${lev}x | 仓位$${pos} | 止损${stopPts}点 | 止盈+$${profit} | RR 1:${rr}`);
    }
    console.log('  ─────────────────────────────────');
  }
}

// ============================================================
// 3. 复利计算器
// ============================================================
function compoundCalc(winRate, avgReturn, trades) {
  console.log('');
  console.log('═══════════════════════════════════════');
  console.log('  复利模拟');
  console.log('  本金: $' + CONFIG.capital + ' | 胜率: ' + (winRate*100) + '% | 单笔收益: ' + (avgReturn*100) + '%');
  console.log('═══════════════════════════════════════');
  let capital = CONFIG.capital;
  let wins = 0, losses = 0;
  for (let i = 1; i <= trades; i++) {
    const win = Math.random() < winRate;
    if (win) { capital *= (1 + avgReturn); wins++; }
    else { capital *= (1 - CONFIG.riskPerTrade); losses++; }
    if (i % 10 === 0 || i === trades) {
      console.log('  ' + i + '笔后: $' + round(capital, 1) + ' | 胜' + wins + ' 负' + losses);
    }
  }
  console.log('  总回报: ' + round((capital/CONFIG.capital - 1)*100, 1) + '%');
}

// ============================================================
// 4. 账户总览
// ============================================================
function accountOverview() {
  okxReq('GET', '/api/v5/account/balance', null, (err, data) => {
    console.log('');
    console.log('═══════════════════════════════════════');
    console.log('  OKX 账户');
    console.log('═══════════════════════════════════════');
    if (err || data.code !== '0') {
      console.log('  连接失败');
      return;
    }
    console.log('  总价值: $' + data.data[0].totalEq);
    data.data[0].details.filter(d => parseFloat(d.availBal) > 0).forEach(d => {
      console.log('  ' + d.ccy + ': ' + d.availBal + ' ≈ $' + d.eqUsd);
    });

    // 查持仓
    okxReq('GET', '/api/v5/account/positions?instId=ETH-USDT-SWAP', null, (err2, data2) => {
      if (data2 && data2.code === '0' && data2.data.length > 0) {
        console.log('');
        console.log('  当前持仓:');
        data2.data.forEach(p => {
          const upl = round(parseFloat(p.upl), 2);
          console.log('  ' + p.posSide + ' | 开仓' + p.avgPx + ' | 标记' + p.markPx + ' | UPL: $' + upl);
        });
      } else {
        console.log('  当前无持仓');
      }
    });
  });
}

// ============================================================
// 5. 下单助手
// ============================================================
function placeOrder(side, entryPrice, marginPct, leverage, stopPts, tpPts) {
  const margin = round(CONFIG.capital * marginPct, 1);
  const posSide = side === 'buy' ? 'long' : 'short';
  const ethPrice = parseFloat(entryPrice);
  const position = margin * leverage;
  const sz = round(position / ethPrice / 100, 2); // 张数 = 合约数/100

  const stopPrice = side === 'buy'
    ? round(ethPrice - stopPts, 1)
    : round(ethPrice + stopPts, 1);
  const tpPrice = side === 'buy'
    ? round(ethPrice + tpPts, 1)
    : round(ethPrice - tpPts, 1);

  console.log('');
  console.log('═══════════════════════════════════════');
  console.log('  订单预览');
  console.log('═══════════════════════════════════════');
  console.log('  方向: ' + posSide);
  console.log('  入场: $' + ethPrice);
  console.log('  保证金: ' + margin + 'U | ' + leverage + 'x | 仓位: $' + position);
  console.log('  止损: $' + stopPrice + ' (' + stopPts + '点, -$' + round(CONFIG.capital * CONFIG.riskPerTrade, 1) + ')');
  console.log('  止盈: $' + tpPrice + ' (+' + tpPts + '点, +$' + round(tpPts/ethPrice*position, 1) + ')');

  const orderBody = JSON.stringify({
    instId: 'ETH-USDT-SWAP',
    tdMode: 'isolated',
    posSide: posSide,
    side: side,
    ordType: 'limit',
    sz: sz.toString(),
    px: ethPrice.toString(),
    lever: leverage.toString(),
    stopLossPx: stopPrice.toString(),
    takeProfitPx: tpPrice.toString()
  });

  console.log('');
  console.log('  提交中...');
  okxReq('POST', '/api/v5/trade/order', orderBody, (err, data) => {
    if (data && data.code === '0') {
      console.log('  ✅ 订单成功! ID: ' + data.data[0].ordId);
    } else {
      console.log('  ❌ 失败: ' + JSON.stringify(data));
    }
  });
}

// ============================================================
// 主路由
// ============================================================
const cmd = process.argv[2];
const args = process.argv.slice(3);

switch (cmd) {
  case 'market':
  case '行情':
    marketSnapshot();
    break;

  case 'calc':
  case '计算':
    compoundCalc(0.5, 0.25, 50);
    break;

  case 'account':
  case '账户':
    accountOverview();
    break;

  case 'order':
  case '下单':
    const entry = parseFloat(args[0]) || 2080;
    const mPct = parseFloat(args[1]) || 0.20;
    const lev = parseInt(args[2]) || 125;
    const stop = parseInt(args[3]) || 8;
    const tp = parseInt(args[4]) || 25;
    placeOrder('buy', entry, mPct, lev, stop, tp);
    break;

  default:
    console.log('');
    console.log('═══ ETH 合约交易中枢 ═══');
    console.log('');
    console.log('  node eth-trader market    实时行情 + 仓位计算');
    console.log('  node eth-trader calc      复利模拟');
    console.log('  node eth-trader account   账户总览');
    console.log('  node eth-trader order <入场> <保证金%> <杠杆> <止损点> <止盈点>');
    console.log('');
    console.log('  示例: node eth-trader order 2082 0.20 125 8 25');
}
