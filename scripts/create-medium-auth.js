#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

function usage() {
  console.error(`Usage:
  node scripts/create-medium-auth.js [options]

Options:
  --output <path>       Output file path (default: medium-auth.json)
  --sid <value>         Medium sid cookie (default: MEDIUM_SESSION_COOKIE)
  --xsrf <value>        Medium xsrf cookie (default: MEDIUM_XSRF_COOKIE)
  --uid <value>         Medium uid cookie (default: MEDIUM_UID_COOKIE)
  --cookie <name=value> Extra cookie; can be repeated
  --expires-days <n>    Expiry window in days (default: 30)

Examples:
  MEDIUM_SESSION_COOKIE='...' node scripts/create-medium-auth.js
  node scripts/create-medium-auth.js --sid '...' --xsrf '...' --output medium-auth.json
`);
}

function parseArgs(argv) {
  const args = {
    output: "medium-auth.json",
    sid: process.env.MEDIUM_SESSION_COOKIE || "",
    xsrf: process.env.MEDIUM_XSRF_COOKIE || "",
    uid: process.env.MEDIUM_UID_COOKIE || "",
    cookies: [],
    expiresDays: 30,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => {
      index += 1;
      if (index >= argv.length) {
        throw new Error(`Missing value for ${arg}`);
      }
      return argv[index];
    };

    if (arg === "--output") args.output = next();
    else if (arg === "--sid") args.sid = next();
    else if (arg === "--xsrf") args.xsrf = next();
    else if (arg === "--uid") args.uid = next();
    else if (arg === "--cookie") args.cookies.push(next());
    else if (arg === "--expires-days") args.expiresDays = Number.parseInt(next(), 10);
    else if (arg === "-h" || arg === "--help") {
      usage();
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  if (!args.sid) {
    throw new Error("A Medium sid cookie is required via --sid or MEDIUM_SESSION_COOKIE");
  }
  if (!Number.isFinite(args.expiresDays) || args.expiresDays <= 0) {
    throw new Error("--expires-days must be a positive number");
  }

  return args;
}

function cookie(name, value, expires, httpOnly = false) {
  return {
    name,
    value,
    domain: ".medium.com",
    path: "/",
    expires,
    httpOnly,
    secure: true,
    sameSite: "Lax",
  };
}

function parseCookiePair(pair) {
  const index = pair.indexOf("=");
  if (index <= 0) {
    throw new Error(`Invalid cookie pair: ${pair}`);
  }
  return [pair.slice(0, index), pair.slice(index + 1)];
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const expires = Math.floor(Date.now() / 1000) + args.expiresDays * 24 * 60 * 60;
  const cookies = [cookie("sid", args.sid, expires, true)];

  if (args.xsrf) cookies.push(cookie("xsrf", args.xsrf, expires));
  if (args.uid) cookies.push(cookie("uid", args.uid, expires));

  for (const pair of args.cookies) {
    const [name, value] = parseCookiePair(pair);
    cookies.push(cookie(name, value, expires));
  }

  const output = {
    cookies,
    origins: [],
  };
  const outputPath = path.resolve(args.output);
  fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  console.log(`Wrote ${outputPath}`);
}

try {
  main();
} catch (error) {
  console.error(`create-medium-auth: ${error.message}`);
  usage();
  process.exit(1);
}
