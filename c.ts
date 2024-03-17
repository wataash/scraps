#!/usr/bin/env node
// SPDX-FileCopyrightText: Copyright (c) 2023-2024 Wataru Ashihara <wataash0607@gmail.com>
// SPDX-License-Identifier: Apache-2.0
// for WebStorm:
// noinspection RegExpRepeatedSpace

/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-constant-condition */
/* eslint-disable no-regex-spaces */

import * as assert from "node:assert";
import * as child_process from "node:child_process";
import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";
import * as repl from "node:repl";
import * as stream from "node:stream";
import * as tty from "node:tty";
import * as url from "node:url";
import * as util from "node:util";

import * as commander from "commander";
import { program } from "commander";
import envPaths from "env-paths";
import esMain from "es-main";
import express from "express";
import * as nodeHtmlParser from "node-html-parser";
import * as parse5 from "parse5";
import * as pty from "node-pty";
import * as puppeteer from "puppeteer-core";

import { Logger } from "./src/logger.js";

const logger = new Logger();

// -----------------------------------------------------------------------------
// lib

class AppError extends Error {
  constructor(message: string, withStack = false) {
    // https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-2.html
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
    if (withStack) {
      logger.errors(message);
    } else {
      logger.error(message);
    }
  }
}

const DIR_CACHE = envPaths(path.join("wataash", "c.ts")).cache;
const DIR_TMP = envPaths(path.join("wataash", "c.ts")).temp;
fs.mkdirSync(DIR_CACHE, { recursive: true });
fs.mkdirSync(DIR_TMP, { recursive: true });

const __filename = url.fileURLToPath(import.meta.url);

function i(object: any): ReturnType<typeof util.inspect> {
  return util.inspect(object, { colors: tty.isatty(process.stdout.fd) });
}

function ii(object: any): ReturnType<typeof util.inspect> {
  return util.inspect(object, { colors: tty.isatty(process.stdout.fd), breakLength: Infinity });
}

// https://github.com/jonschlinkert/isobject/blob/master/index.js
function isObject(value: unknown): value is object {
  return value !== null && typeof value === "object" && Array.isArray(value) === false;
}

class Queue<T> {
  private readonly q: T[];
  private readonly qWaiters: { resolve: (value: "resolved") => void }[];

  constructor() {
    this.q = [];
    this.qWaiters = [];
  }

  push(elem: T): number {
    const ret = this.q.unshift(elem); // XXX: slow; should be real queue
    this.qWaiters.shift()?.resolve("resolved"); // XXX: slow; should be real queue
    return ret;
  }

  async pop(): Promise<T> {
    const ret = this.q.pop();
    if (ret !== undefined) {
      return ret;
    }

    const p = new Promise((resolve) => {
      this.qWaiters.push({ resolve });
    });
    await p;
    const ret2 = this.q.pop();
    if (ret2 === undefined) unreachable();
    return ret2;
  }
}

let reArr: RegExpExecArray | null;

// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions
function regExpEscape(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // $& means the whole matched string
}

// const regExpReplacerEscape = (s: string): string => s.replaceAll("$", "$$$$"); // avoid special replacement with "$" https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace
// const regExpReplacerEscape = (s) => s.replace(/\$/g, "$$$$"); // avoid special replacement with "$" https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace
function regExpReplacerEscape(s: string): string {
  // avoid special replacement with "$"
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace
  return s.replaceAll("$", "$$$$");
}

function sh(cmd: string): string {
  logger.debug(cmd);
  return child_process.execSync(cmd, { encoding: "utf8" });
}

export function sleep(milliSeconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliSeconds));
}

export async function sleepForever(): Promise<never> {
  while (true) {
    // wakeup every 1 second so that debugger can break here
    // eslint-disable-next-line no-await-in-loop
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

// `sh -c ${stringCommandsToShC(["echo", "foo bar"])}`
//
// bash -c 'echo "${@@Q}"' _ echo "foo bar"            # 'echo' 'foo bar'
// bash -c 'echo "${@@Q}"' _ echo ">" "foo bar"        # 'echo' '>' 'foo bar'
// bash -c 'echo "${@@Q}"' _ "echo 'foo bar' > a.txt"  # 'echo '\''foo bar'\'' > a.txt'
//
// a.js echo "foo bar"           # ["echo", "foo bar"]         -> `'echo' 'foo bar'`
// a.js echo ">" "foo bar"       # ["echo", ">", "foo bar"]    -> `'echo' '>' 'foo bar'`
// a.js "echo 'foo bar' > a.txt" # ["echo 'foo bar' > a.txt"]  -> `'echo '\\''foo bar'\\'' > a.txt'`
function stringCommandsToShC(cmds: string[]): string {
  // TODO: implement in js
  const stdout = child_process.execFileSync("bash", ["-c", 'echo "${@@Q}"', "_", ...cmds], { encoding: "utf8" });
  return stdout.trimEnd();
}

// assert.deepStrictEqual(stringCommandsToShC(["echo", "foo bar"]), `'echo' 'foo bar'`);
// assert.deepStrictEqual(stringCommandsToShC(["echo", ">", "foo bar"]), `'echo' '>' 'foo bar'`);
// assert.deepStrictEqual(stringCommandsToShC(["echo 'foo bar' > a.txt"]), `'echo '\\''foo bar'\\'' > a.txt'`);

// stringEmptify("\n a \r\n b \n") // -> "\n\r\n\n"
function stringEmptify(s: string): string {
  const matches = s.match(/\r?\n/g); // ES2020: .matchAll()
  if (matches === null) return "";
  return matches.join("");
}

// "|\n a \r\n b \n" 0  stringEmptifyFromIndex("\n a \r\n b \n", 0) // \n\r\n\n
// "\n| a \r\n b \n" 1  stringEmptifyFromIndex("\n a \r\n b \n", 1) // same
// "\n |a \r\n b \n" 2  stringEmptifyFromIndex("\n a \r\n b \n", 2) // \n \r\n\n
// "\n a| \r\n b \n" 3  stringEmptifyFromIndex("\n a \r\n b \n", 3) // \n a\r\n\n
// "\n a |\r\n b \n" 4  stringEmptifyFromIndex("\n a \r\n b \n", 4) // \n a \r\n\n
// "\n a \r|\n b \n" 5  stringEmptifyFromIndex("\n a \r\n b \n", 5) // same
// "\n a \r\n| b \n" 6  stringEmptifyFromIndex("\n a \r\n b \n", 6) // same
// "\n a \r\n |b \n" 7  stringEmptifyFromIndex("\n a \r\n b \n", 7) // \n a \r\n \n
// "\n a \r\n b| \n" 8  stringEmptifyFromIndex("\n a \r\n b \n", 8) // \n a \r\n b\n
// "\n a \r\n b |\n" 9  stringEmptifyFromIndex("\n a \r\n b \n", 9) // \n a \r\n b \n
// "\n a \r\n b \n|" 10 stringEmptifyFromIndex("\n a \r\n b \n", 10) // \n a \r\n b \n
function stringEmptifyFromIndex(s: string, index: number): string {
  return s.slice(0, index) + stringEmptify(s.slice(index));
}

// "|\n a \r\n b \n" 0  stringEmptifyUntilIndex("\n a \r\n b \n", 0) // \n a \r\n b \n
// "\n| a \r\n b \n" 1  stringEmptifyUntilIndex("\n a \r\n b \n", 1) // same
// "\n |a \r\n b \n" 2  stringEmptifyUntilIndex("\n a \r\n b \n", 2) // \na \r\n b \n
// "\n a| \r\n b \n" 3  stringEmptifyUntilIndex("\n a \r\n b \n", 3) // \n \r\n b \n
// "\n a |\r\n b \n" 4  stringEmptifyUntilIndex("\n a \r\n b \n", 4) // \n\r\n b \n
// "\n a \r|\n b \n" 5  stringEmptifyUntilIndex("\n a \r\n b \n", 5) // \n\n b \n    ! \r\n -> \r
// "\n a \r\n| b \n" 6  stringEmptifyUntilIndex("\n a \r\n b \n", 6) // \n\r\n b \n
// "\n a \r\n |b \n" 7  stringEmptifyUntilIndex("\n a \r\n b \n", 7) // \n\r\nb \n
// "\n a \r\n b| \n" 8  stringEmptifyUntilIndex("\n a \r\n b \n", 8) // \n\r\n \n
// "\n a \r\n b |\n" 9  stringEmptifyUntilIndex("\n a \r\n b \n", 9) // \n\r\n\n
// "\n a \r\n b \n|" 10 stringEmptifyUntilIndex("\n a \r\n b \n", 10) // same
function stringEmptifyUntilIndex(s: string, index: number): string {
  return stringEmptify(s.slice(0, index)) + s.slice(index);
}

// ]]> -> ]]]]><![CDATA[>
function stringEscapeCdata(str: string): string {
  // return str.replaceAll("]]>", "]]]]><![CDATA[>"); // es2021
  return str.replace(/]]>/g, "]]]]><![CDATA[>");
}

// https://stackoverflow.com/questions/1779858/how-do-i-escape-a-string-for-a-shell-command-in-node
function stringEscapeShell(str: string) {
  return `"${str.replace(/(["'$`\\])/g, "\\$1")}"`;
}

function stringFirstLine(s: string): string {
  const i = s.indexOf("\n");
  if (i === -1) return s;
  if (i === 0) return ""; // "\n..."
  // s.at(): es2022
  // if (s.at(i - 1) === "\r") return s.slice(0, i - 1); // "...\r\n..."
  if (s.slice(i - 1, i) === "\r") return s.slice(0, i - 1); // "...\r\n..."
  return s.slice(0, i); // "...\n..."
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function _stringFirstLineTest(): void {
  assert.deepStrictEqual(stringFirstLine(""), "");
  assert.deepStrictEqual(stringFirstLine("\r"), "\r");
  assert.deepStrictEqual(stringFirstLine("\x01"), "\x01"); // ^A
  assert.deepStrictEqual(stringFirstLine("\n"), "");
  assert.deepStrictEqual(stringFirstLine("\r\n"), "");
  assert.deepStrictEqual(stringFirstLine("\n\r"), "");
  assert.deepStrictEqual(stringFirstLine("xxx"), "xxx");
  assert.deepStrictEqual(stringFirstLine("xxx\n"), "xxx");
  assert.deepStrictEqual(stringFirstLine("xxx\r\n"), "xxx");
  assert.deepStrictEqual(stringFirstLine("xxx\n\r"), "xxx");
  assert.deepStrictEqual(stringFirstLine("\nyyy"), "");
  assert.deepStrictEqual(stringFirstLine("\r\nyyy"), "");
  assert.deepStrictEqual(stringFirstLine("xxx\nyyy"), "xxx");
  assert.deepStrictEqual(stringFirstLine("xxx\r\nyyy"), "xxx");
}

function stringNumberOfLines(s: string): number {
  return (s.match(/\n/g) || []).length + 1;
}

function stringRemoveFirstLine(s: string): string {
  const i = s.indexOf("\n");
  if (i === -1) return "";
  return s.slice(i + 1);
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function _stringRemoveFirstLineTest(): void {
  assert.deepStrictEqual(stringRemoveFirstLine(""), "");
  assert.deepStrictEqual(stringRemoveFirstLine("foo"), "");
  assert.deepStrictEqual(stringRemoveFirstLine("foo\n"), "");
  assert.deepStrictEqual(stringRemoveFirstLine("foo\r\n"), "");
  assert.deepStrictEqual(stringRemoveFirstLine("foo\n\r"), "\r");
  assert.deepStrictEqual(stringRemoveFirstLine("\n\n"), "\n");
  assert.deepStrictEqual(stringRemoveFirstLine("\r\n\r\n"), "\r\n");
  assert.deepStrictEqual(stringRemoveFirstLine("foo\n\nbar\nbaz\n"), "\nbar\nbaz\n");
  assert.deepStrictEqual(stringRemoveFirstLine("foo\r\n\r\nbar\r\nbaz\r\n"), "\r\nbar\r\nbaz\r\n");
}

function stringRemoveLastLine(s: string): string {
  return s.replace(/\r?\n$/, "");
}

function stringRemovePrefix(s: string, prefix: string): string {
  return s.replace(new RegExp(`^${regExpEscape(prefix)}`), "");
}

function stringRemoveSuffix(s: string, suffix: string): string {
  return s.replace(new RegExp(`${regExpEscape(suffix)}$`), "");
}

function stringSnip(s: string, len: number) {
  s = s.replaceAll("\n", "⏎");
  if (s.length <= len) return s;
  len = Math.floor(len / 2);
  return `${s.slice(0, len)} ... ${s.slice(s.length - len)}`;
}

function stringTrimTrailingSlashes(s: string): string {
  while (s.at(-1) === "/") {
    s = s.slice(0, -1);
  }
  return s;
}

function unreachable(): never {
  throw new AppError("BUG: unreachable", true);
}

// -----------------------------------------------------------------------------
// cli

export const VERSION = "0.1.0";

export interface OptsGlobal {
  quiet: boolean;
  verbose: number;
  ZHiddenGlobalOption: boolean;
}

// prettier-ignore
program
  .name("c.js")
  .description("mini CLIs")
  .version(VERSION)
  .addOption(new commander.Option("-q, --quiet", "quiet mode").default(false).conflicts("verbose"))
  .addOption(new commander.Option("-v, --verbose", "print verbose output; -vv to print debug output").default(0).argParser(cliIncreaseVerbosity).conflicts("quiet"))
  .addOption(new commander.Option("   ---z-hidden-global-option").hideHelp().default(false))
  .alias(); // dummy

function cliCommandExit(exitStatus: number): void {
  cliCommandExitStatus.push(exitStatus);
  return;
}

const cliCommandExitStatus = new Queue<number>();

function cliCommandInit(): OptsGlobal {
  if (program.opts().quiet === true) {
    logger.level = Logger.Level.Error;
  } else if (program.opts().verbose === 0) {
    logger.level = Logger.Level.Warn;
  } else if (program.opts().verbose === 1) {
    logger.level = Logger.Level.Info;
  } else if (program.opts().verbose >= 1) {
    logger.level = Logger.Level.Debug;
  }

  logger.debug(`${path.basename(__filename)} version ${VERSION} PID ${process.pid}`);
  logger.debug("args: %O", process.argv);

  return program.opts();
}

/* eslint-disable @typescript-eslint/no-unused-vars */
function cliIncreaseVerbosity(value: string /* actually undefined */, previous: number): number {
  return previous + 1;
}

export async function cliMain(): Promise<never> {
  try {
    await program.parse(process.argv);
    const exitStatus = await cliCommandExitStatus.pop();
    process.exit(exitStatus);
  } catch (e) {
    if (e instanceof AppError) {
      // assert.ok(e.constructor.name === "AppError")
      process.exit(1);
    }
    logger.error(`unexpected error: ${e}`);
    throw e;
  }
  unreachable();
}

// -----------------------------------------------------------------------------
// lib for commands

// https://github.com/tj/commander.js#custom-option-processing
// prettier-ignore
function myParseInt(value: string, dummyPrevious?: number): number {
  const parsedValue = Number.parseInt(value, 10);
  if (Number.isNaN(parsedValue))
    throw new commander.InvalidArgumentError("not a number.");
  return parsedValue;
}

function myParseIntPort(value: string, dummyPrevious?: number): number {
  const parsedValue = Number.parseInt(value, 10);
  if (Number.isNaN(parsedValue)) throw new commander.InvalidArgumentError("not a number.");
  if (parsedValue < 0 || parsedValue > 65535) throw new commander.InvalidArgumentError("must be 0-65535.");
  return parsedValue;
}

// -----------------------------------------------------------------------------
// command - 0template @pub
// DON'T FORGET TO REMOVE @pub

program
  .command("0template")
  .description("0template description")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - exec-tsserver-defs @pub
// @ref:qjs-vscode-extension-dev-update

class ExecTSServerDefsHTTPReader {
  private buf = Buffer.from("");
  private readonly waiters: { resolve: (value: unknown) => void }[] = [];
  // stream: stream.Readable;

  constructor(stream: stream.Readable) {
    stream.on("data", (data) => {
      this.buf = Buffer.concat([this.buf, data]);
      for (const waiter of this.waiters) {
        waiter.resolve(null);
      }
    });
  }

  async read(): Promise<Buffer> {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const reArr = /^(Content-Length: (\d+)\r\n\r\n)([\s\S]*)$/.exec(this.buf.toString());
      if (reArr === null) {
        // logger.debug(`no Content-Length; buf:${this.buf}`);
        await new Promise((resolve) => {
          this.waiters.push({ resolve });
        });
        continue;
      }
      if (reArr[3].length < Number.parseInt(reArr[2], 10)) {
        logger.debug(`short read: ${reArr[3].length} < ${reArr[2]}; buf:${this.buf}`);
        await new Promise((resolve) => {
          this.waiters.push({ resolve });
        });
        continue;
      }
      const content = this.buf.subarray(reArr[1].length, reArr[1].length + Number.parseInt(reArr[2], 10));
      if (this.buf.length < reArr[1].length + Number.parseInt(reArr[2], 10)) {
        unreachable();
      }
      this.buf = this.buf.subarray(reArr[1].length + Number.parseInt(reArr[2], 10));
      if (this.buf.length > 0) {
        logger.debug(`leftover: ${this.buf.length} bytes`);
      }
      return content;
    }
    // NOTREACHED
  }
}

program
  .command("exec-tsserver-defs")
  .description("exec-tsserver-defs description")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .allowExcessArguments(false)
  .action(async (opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();

    const read = async (): Promise<string> => {
      const content = (await r.read()).toString();
      if (content.at(-1) !== "\n") {
        throw new AppError(`unexpected: ${content}`);
      }
      logger.info(content.slice(0, -1));
      return content.slice(0, -1);
    };

    const write = (s: string): void => {
      logger.debug(s);
      cp.stdin.write(`${s}\r\n`);
    };

    sh(`mkdir -p /tmp/vscode/`);
    const cp = child_process.spawn("tsserver");
    const r = new ExecTSServerDefsHTTPReader(cp.stdout);
    let resp = await read(); // {"seq":0,"type":"event","event":"typingsInstallerPid","body":{"pid":2463769}}
    assert.ok(JSON.parse(resp).event == "typingsInstallerPid");
    write(`{"type": "request", "seq": 0, "command": "open", "arguments": {"file": "/home/wsh/qjs/vscode-myext0/src/extension.ts"}}`);
    // {"seq":0,"type":"event","event":"projectLoadingStart","body":{"projectName":"/home/wsh/qjs/vscode-myext0/tsconfig.json","reason":"Creating possible configured project for /home/wsh/qjs/vscode-myext0/src/extension.ts to open"}}
    // {"seq":0,"type":"event","event":"projectLoadingFinish","body":{"projectName":"/home/wsh/qjs/vscode-myext0/tsconfig.json"}}
    // {"seq":0,"type":"event","event":"telemetry","body":{"telemetryEventName":"projectInfo","payload":{"projectId":"86a3459aaa58a364e330bce05850fab43aed42a1293c7443e3df01ac897757b0","fileStats":{"js":0,"jsSize":0,"jsx":0,"jsxSize":0,"ts":5,"tsSize":35281,"tsx":0,"tsxSize":0,"dts":205,"dtsSize":3329244,"deferred":0,"deferredSize":0},"compilerOptions":{"module":"node16","target":"es2022","outDir":"","lib":["es2022"],"sourceMap":true,"rootDir":"","strict":true},"typeAcquisition":{"enable":false,"include":false,"exclude":false},"extends":false,"files":false,"include":false,"exclude":false,"compileOnSave":false,"configFileName":"tsconfig.json","projectType":"configured","languageServiceEnabled":true,"version":"5.3.3"}}}
    while (false) {
      resp = await read();
      if (JSON.parse(resp).event == "telemetry") {
        break;
      }
    }
    for (const [i, req] of [
      // prettier-ignore
      `{"type": "request", "seq": 0, "command": "definition", "arguments": {"file": "/home/wsh/qjs/vscode-myext0/src/extension.ts", "line":150, "offset":2}}`,
      `{"type": "request", "seq": 0, "command": "definition", "arguments": {"file": "/home/wsh/qjs/vscode-myext0/src/extension.ts", "line":150, "offset":8}}`,
    ].entries()) {
      write(req.replace(`"seq": 0`, `"seq": ${i + 1}`));
      while (true) {
        resp = await read();
        if (JSON.parse(resp).request_seq === i + 1) {
          break;
        }
      }
      JSON.parse(resp);
    }
    for (const [i, line] of fs.readFileSync("/home/wsh/qjs/vscode-myext0/src/extension.ts", "utf8").split(/\r?\n/).entries()) {
      const reArr = /^\tvscode\.([\w.]+?);\t+\/\//.exec(line);
      if (reArr === null) {
        continue;
      }
      process.stdout.write(`${line}\n`);
      // line.at(reArr[1].length + 2);
      write(`{"type": "request", "seq": ${i + 1}, "command": "definition", "arguments": {"file": "/home/wsh/qjs/vscode-myext0/src/extension.ts", "line":${i + 1}, "offset":${reArr[1].length + 2}}}`);
      while (true) {
        resp = await read();
        if (JSON.parse(resp).request_seq === i + 1) {
          break;
        }
      }
      assert.ok(JSON.parse(resp).body.length >= 1);
      JSON.parse(resp).body[0];
    }

    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - fs-md-code-blocks @pub

program
  .command("fs-md-code-blocks")
  .description("fs-md-code-blocks description")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    sh(`rm -frv /tmp/vscode_md/ && mkdir -p /tmp/vscode_md/`);
    let i = 0;
    let txtBody = "## test\n";
    for (const match of txt.matchAll(/^```(?<l>.+)?(\r?\n)(?<b>[\s\S]+?)(\r?\n)```$/gm)) {
      // const codeBlockLang = match.groups.l; // string?
      // const body = match.groups.b; // string
      // @ts-ignore
      logger.info(`/tmp/vscode_md/${i}.md\t${match.groups.l}\t${(match.groups.b.match(/\n/g) || []).length + 1} lines`);
      txtBody += `\n${match[0]}\n`;
      fs.writeFileSync(`/tmp/md/${i}.md`, txtBody);
      i++;
    }
    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - http-clipboard-server @pub

program
  .command("http-clipboard-server")
  .description("http-clipboard-server description")
  .addOption(new commander.Option("    --port <port>", "port number").default(3000).argParser(myParseIntPort))
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .allowExcessArguments(false)
  .action(async (opts: { port: number; ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const app = express();
    app.use(express.text()); // var type = opts.type || 'text/plain'
    app.get("/", async (req: express.Request, res: express.Response, next: express.NextFunction) => {
      logger.debug(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${ii(req.headers)}`);
      res.setHeader("Content-Type", "text/plain");
      // sh(`clipnotify -s clipboard`);
      res.send(sh(`xsel -b -o`));
    });
    app.post("/", (req: express.Request, res: express.Response, next: express.NextFunction) => {
      logger.debug(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${ii(req.headers)} | ${i(req.body)}`);
      res.setHeader("Content-Type", "text/plain");
      if (typeof req.body !== "string") {
        return res.status(422).send(`invalid request body (${i(req.body)}); not text/plain?`);
      }
      if (req.body === sh(`xsel -b -o`)) {
        // avoid infinite loop between us and them
        res.send(`not_copied\r\n`);
        return;
      }
      child_process.execSync(`xsel -b -i`, { input: req.body });
      res.send(`copied ${req.body.length} bytes\r\n`);
    });
    app.listen(opts.port, () => {
      logger.info(`listening on ${opts.port}`);
    });
    await sleepForever();
    // return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - http-sse-proxy @pub

program
  .command("http-sse-proxy")
  .description("http-sse-proxy description")
  .addOption(new commander.Option("    --port <port>", "port number").default(3000).argParser(myParseIntPort))
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("<url>", "url to SSE-proxy"))
  .allowExcessArguments(false)
  .action(async (url: string, opts: { port: number; ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const app = express();
    app.get("/", async (req: express.Request, res: express.Response, next: express.NextFunction) => {
      logger.info(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${ii(req.headers)}`);
      res.setHeader("Content-Type", "text/event-stream");
      const cp = child_process.spawn(`curl -fSs --no-buffer -X ${req.method} ${stringEscapeShell(url)}`, { shell: true });
      cp.stdout.on("data", (data) => {
        logger.debug(`spawn(): stdout: ${stringSnip(data.toString(), 100)}`);
        // res.send(data);
        if (!res.write(data)) {
          cp.stdout.destroy(); // kill with SIGPIPE
          cp.stderr.destroy();
        }
      });
      cp.stderr.on("data", (data) => {
        logger.error(`spawn(): stderr: ${data}`);
        res.write(data);
      });
      cp.on("close", (code) => {
        logger.info(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${ii(req.headers)} | closed (spawn close code: ${code})`);
      });
    });
    app.listen(opts.port, () => {
      logger.info(`listening on ${opts.port}`);
    });
    await sleepForever();
    // return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - http-sse-tailf @pub

program
  .command("http-sse-tailf")
  .description("http-sse-tailf description")
  .addOption(new commander.Option("    --port <port>", "port number").default(3000).argParser(myParseIntPort))
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { port: number; ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const app = express();
    app.get("/", async (req: express.Request, res: express.Response, next: express.NextFunction) => {
      logger.info(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${ii(req.headers)}`);
      res.setHeader("Content-Type", "text/event-stream");
      const cp = child_process.spawn(`tail -F ${file ? stringEscapeShell(file) : ""}`, { shell: true });
      cp.stdout.on("data", (data) => {
        logger.debug(`spawn(): stdout: ${stringSnip(data.toString(), 100)}`);
        // res.send(data);
        if (!res.write(data)) {
          cp.stdout.destroy(); // kill with SIGPIPE
          cp.stderr.destroy();
        }
      });
      cp.stderr.on("data", (data) => {
        logger.error(`spawn(): stderr: ${data}`);
        res.write(data);
      });
      cp.on("close", (code) => {
        logger.info(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${ii(req.headers)} | closed (spawn close code: ${code})`);
      });
    });
    app.listen(opts.port, () => {
      logger.info(`listening on ${opts.port}`);
    });
    await sleepForever();
    // return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - pty-cmd @pub

program
  .command("pty-cmd")
  .description("pty-cmd description")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("<cmd...>", "run <cmd> in a new pty"))
  .allowExcessArguments(false)
  .action(async (cmd: string[], opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();

    const exitCode = new Queue<number>();

    // Ubuntu 20.04: $TERM default is xterm?
    // systemd-run --user -- (which c.js) pty-cmd -- env  # TERM=xterm
    const ptyProcess = pty.spawn("sh", ["-c", stringCommandsToShC(cmd)], {
      // name: 'xterm-color',
      cols: process.stdout.columns,
      rows: process.stdout.rows,
    } as pty.IPtyForkOptions);

    ptyProcess.onData((data) => {
      // c.js -vv pty-cmd -- /bin/echo -e 'a\x01z'  # [<- cmd](5) [ 'a', '\x01', 'z', '\r', '\n' ]   \x01: ^A
      // c.js -vv pty-cmd -- /bin/echo -e 'a\xffz'  # [<- cmd](5) [ 'a', '�', 'z', '\r', '\n' ]      \xff: invalid utf8 -> �
      logger.debug(`[<- cmd](${data.length}) %O`, ...data);
      process.stdout.write(data);
    });

    ptyProcess.onExit((e) => {
      logger.info(`[cmd exit] exitCode:${e.exitCode} signal:${e.signal}`);
      // should dispose .onData()/.onExit() ?
      exitCode.push(e.exitCode);
    });

    if (tty.isatty(process.stdin.fd)) {
      process.stdin.setRawMode(true);
    } else {
      logger.info("stdin is not a tty; skip stdin.setRawMode(true)");
    }
    let tilde = false;
    process.stdin.on("data", (data: Buffer) => {
      const byteArray = [...data];
      logger.debug(`[-> cmd](${data.length}) ${i([...data.toString()])}`);

      switch (ptyCmdHandleEscape(ptyProcess, data, tilde)) {
        case "in_tilde":
          tilde = true;
          return;
        case "out_tilde":
          tilde = false;
          break;
        case "exit":
          exitCode.push(0);
          // send EOF?
          // dispose process.stdin.on() ?
          return;
      }

      // // ^C
      // if (byteArray[0] === 3) {
      //   logger.warn("^C")
      //   exitCode.push(0);
      // }

      ptyProcess.write(data.toString());
    });

    // // never fired in .setRawMode(trues)
    // process.on("SIGINT", () => {
    //   logger.warn("SIGINT");
    // });

    process.on("SIGWINCH", () => {
      logger.debug(`SIGWINCH -> ${process.stdout.columns}x${process.stdout.rows}`);
      ptyProcess.resize(process.stdout.columns, process.stdout.rows);
    });

    return cliCommandExit(await exitCode.pop());
  });

function ptyCmdHandleEscape(ptyProcess: pty.IPty, data: Buffer, previousTilde: boolean): "in_tilde" | "out_tilde" | "exit" {
  // paste ~. -> byteArray.length === 2, not triggered
  // if (byteArray.length === 1 && byteArray[0] === 0x7e) {
  if (!previousTilde && data.length === 1 && data.toString() === "~") {
    logger.debug("store ~");
    return "in_tilde";
  }

  if (previousTilde) {
    // if (byteArray.length === 1 && byteArray[0] === 0x2e) {
    if (data.length === 1 && data.toString() === ".") {
      logger.info("~. -> exit");
      return "exit";
    }
    logger.debug("release ~");
    ptyProcess.write("~");
    // ptyProcess.write(0x7e);
    if (data.toString() === "~") {
      return "out_tilde";
    }
  }
  return "out_tilde";
}

// -----------------------------------------------------------------------------
// command - txt-emoji @pub

// https://github.com/mathiasbynens/emoji-regex/blob/v10.3.0/index.js#L3
const emojiRegex =
  /[#*0-9]\uFE0F?\u20E3|[\xA9\xAE\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9\u21AA\u231A\u231B\u2328\u23CF\u23ED-\u23EF\u23F1\u23F2\u23F8-\u23FA\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB\u25FC\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615\u2618\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642\u2648-\u2653\u265F\u2660\u2663\u2665\u2666\u2668\u267B\u267E\u267F\u2692\u2694-\u2697\u2699\u269B\u269C\u26A0\u26A7\u26AA\u26B0\u26B1\u26BD\u26BE\u26C4\u26C8\u26CF\u26D1\u26E9\u26F0-\u26F5\u26F7\u26F8\u26FA\u2702\u2708\u2709\u270F\u2712\u2714\u2716\u271D\u2721\u2733\u2734\u2744\u2747\u2757\u2763\u27A1\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B55\u3030\u303D\u3297\u3299]\uFE0F?|[\u261D\u270C\u270D](?:\uFE0F|\uD83C[\uDFFB-\uDFFF])?|[\u270A\u270B](?:\uD83C[\uDFFB-\uDFFF])?|[\u23E9-\u23EC\u23F0\u23F3\u25FD\u2693\u26A1\u26AB\u26C5\u26CE\u26D4\u26EA\u26FD\u2705\u2728\u274C\u274E\u2753-\u2755\u2795-\u2797\u27B0\u27BF\u2B50]|\u26D3\uFE0F?(?:\u200D\uD83D\uDCA5)?|\u26F9(?:\uFE0F|\uD83C[\uDFFB-\uDFFF])?(?:\u200D[\u2640\u2642]\uFE0F?)?|\u2764\uFE0F?(?:\u200D(?:\uD83D\uDD25|\uD83E\uDE79))?|\uD83C(?:[\uDC04\uDD70\uDD71\uDD7E\uDD7F\uDE02\uDE37\uDF21\uDF24-\uDF2C\uDF36\uDF7D\uDF96\uDF97\uDF99-\uDF9B\uDF9E\uDF9F\uDFCD\uDFCE\uDFD4-\uDFDF\uDFF5\uDFF7]\uFE0F?|[\uDF85\uDFC2\uDFC7](?:\uD83C[\uDFFB-\uDFFF])?|[\uDFC4\uDFCA](?:\uD83C[\uDFFB-\uDFFF])?(?:\u200D[\u2640\u2642]\uFE0F?)?|[\uDFCB\uDFCC](?:\uFE0F|\uD83C[\uDFFB-\uDFFF])?(?:\u200D[\u2640\u2642]\uFE0F?)?|[\uDCCF\uDD8E\uDD91-\uDD9A\uDE01\uDE1A\uDE2F\uDE32-\uDE36\uDE38-\uDE3A\uDE50\uDE51\uDF00-\uDF20\uDF2D-\uDF35\uDF37-\uDF43\uDF45-\uDF4A\uDF4C-\uDF7C\uDF7E-\uDF84\uDF86-\uDF93\uDFA0-\uDFC1\uDFC5\uDFC6\uDFC8\uDFC9\uDFCF-\uDFD3\uDFE0-\uDFF0\uDFF8-\uDFFF]|\uDDE6\uD83C[\uDDE8-\uDDEC\uDDEE\uDDF1\uDDF2\uDDF4\uDDF6-\uDDFA\uDDFC\uDDFD\uDDFF]|\uDDE7\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEF\uDDF1-\uDDF4\uDDF6-\uDDF9\uDDFB\uDDFC\uDDFE\uDDFF]|\uDDE8\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDEE\uDDF0-\uDDF5\uDDF7\uDDFA-\uDDFF]|\uDDE9\uD83C[\uDDEA\uDDEC\uDDEF\uDDF0\uDDF2\uDDF4\uDDFF]|\uDDEA\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDED\uDDF7-\uDDFA]|\uDDEB\uD83C[\uDDEE-\uDDF0\uDDF2\uDDF4\uDDF7]|\uDDEC\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEE\uDDF1-\uDDF3\uDDF5-\uDDFA\uDDFC\uDDFE]|\uDDED\uD83C[\uDDF0\uDDF2\uDDF3\uDDF7\uDDF9\uDDFA]|\uDDEE\uD83C[\uDDE8-\uDDEA\uDDF1-\uDDF4\uDDF6-\uDDF9]|\uDDEF\uD83C[\uDDEA\uDDF2\uDDF4\uDDF5]|\uDDF0\uD83C[\uDDEA\uDDEC-\uDDEE\uDDF2\uDDF3\uDDF5\uDDF7\uDDFC\uDDFE\uDDFF]|\uDDF1\uD83C[\uDDE6-\uDDE8\uDDEE\uDDF0\uDDF7-\uDDFB\uDDFE]|\uDDF2\uD83C[\uDDE6\uDDE8-\uDDED\uDDF0-\uDDFF]|\uDDF3\uD83C[\uDDE6\uDDE8\uDDEA-\uDDEC\uDDEE\uDDF1\uDDF4\uDDF5\uDDF7\uDDFA\uDDFF]|\uDDF4\uD83C\uDDF2|\uDDF5\uD83C[\uDDE6\uDDEA-\uDDED\uDDF0-\uDDF3\uDDF7-\uDDF9\uDDFC\uDDFE]|\uDDF6\uD83C\uDDE6|\uDDF7\uD83C[\uDDEA\uDDF4\uDDF8\uDDFA\uDDFC]|\uDDF8\uD83C[\uDDE6-\uDDEA\uDDEC-\uDDF4\uDDF7-\uDDF9\uDDFB\uDDFD-\uDDFF]|\uDDF9\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDED\uDDEF-\uDDF4\uDDF7\uDDF9\uDDFB\uDDFC\uDDFF]|\uDDFA\uD83C[\uDDE6\uDDEC\uDDF2\uDDF3\uDDF8\uDDFE\uDDFF]|\uDDFB\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDEE\uDDF3\uDDFA]|\uDDFC\uD83C[\uDDEB\uDDF8]|\uDDFD\uD83C\uDDF0|\uDDFE\uD83C[\uDDEA\uDDF9]|\uDDFF\uD83C[\uDDE6\uDDF2\uDDFC]|\uDF44(?:\u200D\uD83D\uDFEB)?|\uDF4B(?:\u200D\uD83D\uDFE9)?|\uDFC3(?:\uD83C[\uDFFB-\uDFFF])?(?:\u200D(?:[\u2640\u2642]\uFE0F?(?:\u200D\u27A1\uFE0F?)?|\u27A1\uFE0F?))?|\uDFF3\uFE0F?(?:\u200D(?:\u26A7\uFE0F?|\uD83C\uDF08))?|\uDFF4(?:\u200D\u2620\uFE0F?|\uDB40\uDC67\uDB40\uDC62\uDB40(?:\uDC65\uDB40\uDC6E\uDB40\uDC67|\uDC73\uDB40\uDC63\uDB40\uDC74|\uDC77\uDB40\uDC6C\uDB40\uDC73)\uDB40\uDC7F)?)|\uD83D(?:[\uDC3F\uDCFD\uDD49\uDD4A\uDD6F\uDD70\uDD73\uDD76-\uDD79\uDD87\uDD8A-\uDD8D\uDDA5\uDDA8\uDDB1\uDDB2\uDDBC\uDDC2-\uDDC4\uDDD1-\uDDD3\uDDDC-\uDDDE\uDDE1\uDDE3\uDDE8\uDDEF\uDDF3\uDDFA\uDECB\uDECD-\uDECF\uDEE0-\uDEE5\uDEE9\uDEF0\uDEF3]\uFE0F?|[\uDC42\uDC43\uDC46-\uDC50\uDC66\uDC67\uDC6B-\uDC6D\uDC72\uDC74-\uDC76\uDC78\uDC7C\uDC83\uDC85\uDC8F\uDC91\uDCAA\uDD7A\uDD95\uDD96\uDE4C\uDE4F\uDEC0\uDECC](?:\uD83C[\uDFFB-\uDFFF])?|[\uDC6E\uDC70\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4\uDEB5](?:\uD83C[\uDFFB-\uDFFF])?(?:\u200D[\u2640\u2642]\uFE0F?)?|[\uDD74\uDD90](?:\uFE0F|\uD83C[\uDFFB-\uDFFF])?|[\uDC00-\uDC07\uDC09-\uDC14\uDC16-\uDC25\uDC27-\uDC3A\uDC3C-\uDC3E\uDC40\uDC44\uDC45\uDC51-\uDC65\uDC6A\uDC79-\uDC7B\uDC7D-\uDC80\uDC84\uDC88-\uDC8E\uDC90\uDC92-\uDCA9\uDCAB-\uDCFC\uDCFF-\uDD3D\uDD4B-\uDD4E\uDD50-\uDD67\uDDA4\uDDFB-\uDE2D\uDE2F-\uDE34\uDE37-\uDE41\uDE43\uDE44\uDE48-\uDE4A\uDE80-\uDEA2\uDEA4-\uDEB3\uDEB7-\uDEBF\uDEC1-\uDEC5\uDED0-\uDED2\uDED5-\uDED7\uDEDC-\uDEDF\uDEEB\uDEEC\uDEF4-\uDEFC\uDFE0-\uDFEB\uDFF0]|\uDC08(?:\u200D\u2B1B)?|\uDC15(?:\u200D\uD83E\uDDBA)?|\uDC26(?:\u200D(?:\u2B1B|\uD83D\uDD25))?|\uDC3B(?:\u200D\u2744\uFE0F?)?|\uDC41\uFE0F?(?:\u200D\uD83D\uDDE8\uFE0F?)?|\uDC68(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:\uDC8B\u200D\uD83D)?\uDC68|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D(?:[\uDC68\uDC69]\u200D\uD83D(?:\uDC66(?:\u200D\uD83D\uDC66)?|\uDC67(?:\u200D\uD83D[\uDC66\uDC67])?)|[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uDC66(?:\u200D\uD83D\uDC66)?|\uDC67(?:\u200D\uD83D[\uDC66\uDC67])?)|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]))|\uD83C(?:\uDFFB(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:\uDC8B\u200D\uD83D)?\uDC68\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D\uDC68\uD83C[\uDFFC-\uDFFF])))?|\uDFFC(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:\uDC8B\u200D\uD83D)?\uDC68\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D\uDC68\uD83C[\uDFFB\uDFFD-\uDFFF])))?|\uDFFD(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:\uDC8B\u200D\uD83D)?\uDC68\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D\uDC68\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF])))?|\uDFFE(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:\uDC8B\u200D\uD83D)?\uDC68\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D\uDC68\uD83C[\uDFFB-\uDFFD\uDFFF])))?|\uDFFF(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:\uDC8B\u200D\uD83D)?\uDC68\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D\uDC68\uD83C[\uDFFB-\uDFFE])))?))?|\uDC69(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:\uDC8B\u200D\uD83D)?[\uDC68\uDC69]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D(?:[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uDC66(?:\u200D\uD83D\uDC66)?|\uDC67(?:\u200D\uD83D[\uDC66\uDC67])?|\uDC69\u200D\uD83D(?:\uDC66(?:\u200D\uD83D\uDC66)?|\uDC67(?:\u200D\uD83D[\uDC66\uDC67])?))|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]))|\uD83C(?:\uDFFB(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:[\uDC68\uDC69]|\uDC8B\u200D\uD83D[\uDC68\uDC69])\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D[\uDC68\uDC69]\uD83C[\uDFFC-\uDFFF])))?|\uDFFC(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:[\uDC68\uDC69]|\uDC8B\u200D\uD83D[\uDC68\uDC69])\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D[\uDC68\uDC69]\uD83C[\uDFFB\uDFFD-\uDFFF])))?|\uDFFD(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:[\uDC68\uDC69]|\uDC8B\u200D\uD83D[\uDC68\uDC69])\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D[\uDC68\uDC69]\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF])))?|\uDFFE(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:[\uDC68\uDC69]|\uDC8B\u200D\uD83D[\uDC68\uDC69])\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D[\uDC68\uDC69]\uD83C[\uDFFB-\uDFFD\uDFFF])))?|\uDFFF(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D\uD83D(?:[\uDC68\uDC69]|\uDC8B\u200D\uD83D[\uDC68\uDC69])\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83D[\uDC68\uDC69]\uD83C[\uDFFB-\uDFFE])))?))?|\uDC6F(?:\u200D[\u2640\u2642]\uFE0F?)?|\uDD75(?:\uFE0F|\uD83C[\uDFFB-\uDFFF])?(?:\u200D[\u2640\u2642]\uFE0F?)?|\uDE2E(?:\u200D\uD83D\uDCA8)?|\uDE35(?:\u200D\uD83D\uDCAB)?|\uDE36(?:\u200D\uD83C\uDF2B\uFE0F?)?|\uDE42(?:\u200D[\u2194\u2195]\uFE0F?)?|\uDEB6(?:\uD83C[\uDFFB-\uDFFF])?(?:\u200D(?:[\u2640\u2642]\uFE0F?(?:\u200D\u27A1\uFE0F?)?|\u27A1\uFE0F?))?)|\uD83E(?:[\uDD0C\uDD0F\uDD18-\uDD1F\uDD30-\uDD34\uDD36\uDD77\uDDB5\uDDB6\uDDBB\uDDD2\uDDD3\uDDD5\uDEC3-\uDEC5\uDEF0\uDEF2-\uDEF8](?:\uD83C[\uDFFB-\uDFFF])?|[\uDD26\uDD35\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD\uDDCF\uDDD4\uDDD6-\uDDDD](?:\uD83C[\uDFFB-\uDFFF])?(?:\u200D[\u2640\u2642]\uFE0F?)?|[\uDDDE\uDDDF](?:\u200D[\u2640\u2642]\uFE0F?)?|[\uDD0D\uDD0E\uDD10-\uDD17\uDD20-\uDD25\uDD27-\uDD2F\uDD3A\uDD3F-\uDD45\uDD47-\uDD76\uDD78-\uDDB4\uDDB7\uDDBA\uDDBC-\uDDCC\uDDD0\uDDE0-\uDDFF\uDE70-\uDE7C\uDE80-\uDE88\uDE90-\uDEBD\uDEBF-\uDEC2\uDECE-\uDEDB\uDEE0-\uDEE8]|\uDD3C(?:\u200D[\u2640\u2642]\uFE0F?|\uD83C[\uDFFB-\uDFFF])?|\uDDCE(?:\uD83C[\uDFFB-\uDFFF])?(?:\u200D(?:[\u2640\u2642]\uFE0F?(?:\u200D\u27A1\uFE0F?)?|\u27A1\uFE0F?))?|\uDDD1(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83E\uDDD1|\uDDD1\u200D\uD83E\uDDD2(?:\u200D\uD83E\uDDD2)?|\uDDD2(?:\u200D\uD83E\uDDD2)?))|\uD83C(?:\uDFFB(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1\uD83C[\uDFFC-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83E\uDDD1\uD83C[\uDFFB-\uDFFF])))?|\uDFFC(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1\uD83C[\uDFFB\uDFFD-\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83E\uDDD1\uD83C[\uDFFB-\uDFFF])))?|\uDFFD(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83E\uDDD1\uD83C[\uDFFB-\uDFFF])))?|\uDFFE(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1\uD83C[\uDFFB-\uDFFD\uDFFF]|\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83E\uDDD1\uD83C[\uDFFB-\uDFFF])))?|\uDFFF(?:\u200D(?:[\u2695\u2696\u2708]\uFE0F?|\u2764\uFE0F?\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1\uD83C[\uDFFB-\uDFFE]|\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E(?:[\uDDAF\uDDBC\uDDBD](?:\u200D\u27A1\uFE0F?)?|[\uDDB0-\uDDB3]|\uDD1D\u200D\uD83E\uDDD1\uD83C[\uDFFB-\uDFFF])))?))?|\uDEF1(?:\uD83C(?:\uDFFB(?:\u200D\uD83E\uDEF2\uD83C[\uDFFC-\uDFFF])?|\uDFFC(?:\u200D\uD83E\uDEF2\uD83C[\uDFFB\uDFFD-\uDFFF])?|\uDFFD(?:\u200D\uD83E\uDEF2\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF])?|\uDFFE(?:\u200D\uD83E\uDEF2\uD83C[\uDFFB-\uDFFD\uDFFF])?|\uDFFF(?:\u200D\uD83E\uDEF2\uD83C[\uDFFB-\uDFFE])?))?)/g;

if (false) {
  // https://github.com/mathiasbynens/emoji-regex/tree/v10.3.0
  const text = `
    \u{231A}: ⌚ default emoji presentation character (Emoji_Presentation)
    \u{2194}\u{FE0F}: ↔️ default text presentation character rendered as emoji
    \u{1F469}: 👩 emoji modifier base (Emoji_Modifier_Base)
    \u{1F469}\u{1F3FF}: 👩🏿 emoji modifier base followed by a modifier
  `;
  text.match(emojiRegex); // [⌚, ⌚, ↔️, ↔️, 👩, 👩, 👩🏿, 👩🏿]
  // @ts-ignore
  text.match(emojiRegex).map((emoji) => emoji.length); // [1, 1, 2, 2, 2, 2, 4, 4] bytes?
  // @ts-ignore
  text.match(emojiRegex).map((emoji) => [...emoji]); // [["⌚"], ["⌚"], ["↔", "️"], ["↔", "️"], ["👩"], ["👩"], ["👩", "🏿"], ["👩", "🏿"]] code points
  // @ts-ignore
  text.match(emojiRegex).map((emoji) => [...emoji].length); // [1, 1, 2, 2, 1, 1, 2, 2] code points
}

program
  .command("txt-emoji")
  .description("txt-emoji description")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    for (const emoji of txt.match(emojiRegex) ?? []) {
      process.stdout.write(`${emoji}\n`);
    }
    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - txt-emoji-count @pub

program
  .command("txt-emoji-count")
  .description("txt-emoji-count description")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    const counts: { [key: string]: number } = {};
    for (const emoji of txt.match(emojiRegex) ?? []) {
      counts[emoji] = (counts[emoji] ?? 0) + 1;
    }
    // for (const [emoji, count] of Object.entries(counts))
    //   process.stdout.write(`${count} ${emoji}\n`);
    let i = 0;
    for (const [emoji, count] of Object.entries(counts).sort((a, b) => b[1] - a[1])) {
      process.stdout.write(`${++i}\t${count}\t${emoji}\n`);
    }
    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - txt-extrace-prettify @pub

/*
 2月 11 22:36:07     13261+ <root> /usr/lib/snapd/snap-device-helper change snap_cups_cupsd /devices/pci0000:00/0000:00:14.0/usb1/1-9 189:2
 2月 11 22:36:07     13261- /usr/lib/snapd/snap-device-help exited status=0 time=0.001s
↓
 2月 11 22:36:07     13261[0 0.001s] <root> /usr/lib/snapd/snap-device-helper change snap_cups_cupsd /devices/pci0000:00/0000:00:14.0/usb1/1-9 189:2

 2月 11 22:36:27           13280+ <root> sh -c 'grep -G "^blacklist.*nvidia[[:space:]]*$" /etc/modprobe.d/*.conf'
 ...
 2月 11 22:36:27           13280- sh exited status=1 time=0.001s
↓
 2月 11 22:36:27           13280[1 0.001s] <root> sh -c 'grep -G "^blacklist.*nvidia[[:space:]]*$" /etc/modprobe.d/*.conf'
 ...
*/

program
  .command("txt-extrace-prettify")
  .description("prettify `sudo extrace -tu | ts` output")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    let txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    {
      const matches = [...txt.matchAll(/^(?<date>.+?)(?<spacePID>\s+\d+)\+ (?<cmd>.+)\n.+?\k<spacePID>- .+? exited status=(?<status>\d+) time=(?<time>.+?)s$/gm)]
      for (const match of matches) {
        txt = txt.replace(match[0], regExpReplacerEscape(`${match.groups?.date}${match.groups?.spacePID}[${match.groups?.status} ${match.groups?.time}s] ${match.groups?.cmd}`));
      }
    }
    {
      const matches = [...txt.matchAll(/^(?<date>.+?)(?<spacePID>\s+\d+)\+ (?<cmd>.+)$/gm)]
      for (const match of matches) {
        const reArr = new RegExp(String.raw`^(?<date>.+?)${match.groups?.spacePID}- (?<cmd>.+) exited status=(?<status>\d+) time=(?<time>0.00\d)s\n`, "gm").exec(txt);
        if (reArr === null) continue;
        txt = txt.replace(match[0], regExpReplacerEscape(`${match.groups?.date}${match.groups?.spacePID}[${reArr.groups?.status} ${reArr.groups?.time}s] ${match.groups?.cmd}`));
        txt = txt.replace(reArr[0], "");
      }
    }
    process.stdout.write(txt);
    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - txt-fish-history-edit @pub

program
  .command("txt-fish-history-edit")
  .description("txt-fish-history-edit description")
  .addOption(new commander.Option("    --grep <pattern>").conflicts(["merge", "sort-len"]))
  .addOption(new commander.Option("    --merge <file>").conflicts(["grep", "sort-len"]))
  .addOption(new commander.Option("    --sort-len").conflicts(["grep", "merge"]).default(false))
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { grep?: string, merge?: string, sortLen: boolean, ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    const matches = [...txt.matchAll(/^# (?<date>\d\d\d\d年\d\d月\d\d日 \d\d時\d\d分\d\d秒)(\r?\n)(?<cmd>[\s\S]+?)(?=\r?\n(# \d\d\d\d年\d\d月\d\d日 \d\d時\d\d分\d\d秒|$))/gm)];

    if (opts.grep !== undefined) {
      for (const match of matches) {
        if (!new RegExp(opts.grep).test(match.groups!.cmd)) continue;
        process.stdout.write(`${match[0]}\n`);
      }
      return cliCommandExit(0);
    }

    if (opts.merge !== undefined) {
      const set = new Set(matches.map((match) => JSON.stringify({ date: match.groups?.date, cmd: match.groups?.cmd })));
      const txt2 = fs.readFileSync(opts.merge, "utf8");
      const matches2 = [...txt2.matchAll(/^# (?<date>\d\d\d\d年\d\d月\d\d日 \d\d時\d\d分\d\d秒)(\r?\n)(?<cmd>[\s\S]+?)(?=\r?\n(# \d\d\d\d年\d\d月\d\d日 \d\d時\d\d分\d\d秒|$))/gm)];
      const set2 = new Set(matches2.map((match) => JSON.stringify({ date: match.groups?.date, cmd: match.groups?.cmd })));
      const mergedSet = new Set([...set, ...set2]);
      const mergedArr = [...mergedSet];
      mergedArr.sort();
      for (const j of mergedArr.reverse()) {
        const json = JSON.parse(j);
        process.stdout.write(`# ${json.date}\n${json.cmd}\n`);
      }
      return cliCommandExit(0);
    }

    if (opts.sortLen) {
      // .toSorted(): es2023
      // for (const match of matches.toSorted((a, b) => (a.groups?.cmd.length ?? 0) - (b.groups?.cmd.length ?? 0))) {
      for (const match of matches.sort((a, b) => (a.groups?.cmd.length ?? 0) - (b.groups?.cmd.length ?? 0))) {
        process.stdout.write(`# ${match.groups?.date} ${Buffer.from(match.groups!.cmd).toString("base64")}\n${match.groups?.cmd}\n`);
      }
      return cliCommandExit(0);
    }

    // max length and its index of matches[*].groups.cmd
    if (false) {
      const [cmdLenMaxIndex, cmdLenMax] = matches.reduce(([iMax, lenMax], match, i) => {
        const len = match.groups?.cmd.length ?? 0;
        return lenMax < len ? [i, len] : [iMax, lenMax];
      }, [-1, 0]);
    }

    // create edit file

    const cmdLenMax = Math.max(...matches.map((match) => match.groups?.cmd.length ?? 0));

    const matchesNoNL: RegExpMatchArray[] = [];
    // exclude \n
    for (const match of matches) {
      if (match.groups?.cmd?.includes("\n")) {
        logger.warn(`ignore command with newline: ${match.groups?.cmd}`);
      }
      matchesNoNL.push(match);
    }

    for (const match of matches) {
      process.stdout.write(`${match.groups?.cmd.padEnd(cmdLenMax, " ")} #__date__ ${match.groups?.date} __b64__ ${Buffer.from(match.groups?.cmd as string).toString("base64")}\n`);
    }

    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - txt-html-cdata-b64 @pub

program
  .command("txt-html-cdata-b64")
  .description("txt-html-cdata-b64 description")
  .addOption(new commander.Option("   ---z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    if (opts.ZTest) {
      const in_ = `\
<div>
  <pre><![CDATA[foo
bar
]]></pre>
</div>
`;
      const out = `\
<div>
  <pre><CDATA>PCFbQ0RBVEFbZm9vCmJhcgpdXT4=</CDATA></pre>
</div>
`;
      assert.strictEqual(txtHTMLCDataB64(in_), out);
      return cliCommandExit(0);
    }
    process.stdout.write(txtHTMLCDataB64(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
    return cliCommandExit(0);
  });

function txtHTMLCDataB64(html: string): string {
  for (const match of html.matchAll(/<!\[CDATA\[[\s\S]*?]]>/g)) {
    html = html.replace(match[0], `<CDATA>${Buffer.from(match[0]).toString("base64")}</CDATA>`);
  }
  return html;
}
// -----------------------------------------------------------------------------
// command - txt-html-cdata-b64d @pub

program
  .command("txt-html-cdata-b64d")
  .description("txt-html-cdata-b64d description")
  .addOption(new commander.Option("   ---z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    if (opts.ZTest) {
      const in_ = `\
<div>
  <pre><CDATA>PCFbQ0RBVEFbZm9vCmJhcgpdXT4=</CDATA></pre>
</div>
`;
      const out = `\
<div>
  <pre><![CDATA[foo
bar
]]></pre>
</div>
`;
      assert.strictEqual(txtHTMLCDataB64d(in_), out);
      assert.strictEqual(out, txtHTMLCDataB64d(txtHTMLCDataB64(out)));
      return cliCommandExit(0);
    }
    process.stdout.write(txtHTMLCDataB64d(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
    return cliCommandExit(0);
  });

function txtHTMLCDataB64d(html: string): string {
  for (const match of html.matchAll(/<CDATA>(.+?)<\/CDATA>/g)) {
    html = html.replace(match[0], regExpReplacerEscape(`${Buffer.from(match[1], "base64").toString("utf8")}`));
  }
  return html;
}

// -----------------------------------------------------------------------------
// command - txt-html-break @pub

// abort

program
  .command("txt-html-break")
  .description("txt-html-break description")
  .addOption(new commander.Option("   ---z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    if (opts.ZTest) {
      const testCase = `\
 <div> <div> x <pre><![CDATA[line 1<>
line 2<>]]> </pre> y </div> </div>
 $
↓
 <div>
<div>
x
<pre><![CDATA[line 1<>
line 2<>]]>
</pre>
y
</div>
</div>
 $
----------
 <div> <div>x <pre><![CDATA[line 1<>
line 2<>]]> </pre>y </div> </div>
 $
↓
 <div>
<div>x
<pre><![CDATA[line 1<>
line 2<>]]>
</pre>y
</div>
</div>
 $
----------
 <div> <div> x<pre><![CDATA[line 1<>
line 2<>]]> </pre> y</div> </div>
 $
↓
 <div>
<div>
x<pre><![CDATA[line 1<>
line 2<>]]>
</pre>
y</div>
</div>
 $
----------
 <div> <div>x<pre><![CDATA[line 1<>
line 2<>]]></pre>y</div> </div>
 $
↓
 <div>
<div>x<pre><![CDATA[line 1<>
line 2<>]]></pre>y</div>
</div>
 $`;
      testCase.replaceAll(/\$$/gm, "").split("\n----------\n").map((s) => s.split("\n↓\n")).forEach(([in_, expected]) => {
        const actual = txtHTMLBreak(in_);
        assert.strictEqual(actual, expected);
      });
      return cliCommandExit(0);
    }
    process.stdout.write(txtHTMLBreak(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
    return cliCommandExit(0);
  });

function txtHTMLBreak(html: string): string {
  const offsets = [{offset: -1, kind: "dummy"}];
  // @ts-ignore
  const assert = (expr) => {
    if (!expr) {
      throw "BUG";
    }
  }
  const dig = (node: any)  => {
    if (node.nodeName === "#document") {
      assert(("childNodes" in node));
      assert(!("tagName" in node));
    } else if (node.nodeName === "#text") {
      assert(!("childNodes" in node));
      assert(!("tagName" in node));
    } else if (node.nodeName === "#comment") {
      // comment or CDATA
      assert(!("childNodes" in node));
      assert(!("tagName" in node));
    } else {
      // tag
      assert(("childNodes" in node));
      assert(("tagName" in node));
    }
    if ("sourceCodeLocation" in node && node.sourceCodeLocation !== null) {
      // @ts-ignore
      assert(node.sourceCodeLocation.startOffset >= offsets.at(-1).offset);
      offsets.push({offset: node.sourceCodeLocation.startOffset, kind: `|${node.nodeName}`});
    }
    if (("childNodes" in node)) {
      for (const n of node.childNodes) {
        dig(n);
      }
    }
    if ("sourceCodeLocation" in node && node.sourceCodeLocation !== null) {
      // @ts-ignore
      assert(node.sourceCodeLocation.endOffset >= offsets.at(-1).offset);
      offsets.push({ offset: node.sourceCodeLocation.endOffset, kind: `${node.nodeName}|` });
    }
  }
  html = txtHTMLCDataB64(html); // without this: <![CDATA[>]]> is treated as "<!-- [CDATA[ -->" and "]]>"
  const document = parse5.parse(html, {sourceCodeLocationInfo: true});
  dig(document);
  assert(offsets[0].offset === -1);
  offsets.shift();
  offsets.reverse();
  for (const offset of offsets) {
    if (offset.kind === "|#text" && html[offset.offset - 1 ] !== "\n" && html[offset.offset] === " " && html[offset.offset + 1] !== "\r" && html[offset.offset + 1] !== "\n") {
      // console.log(`${offset.offset - 1}${html[offset.offset- 1]}${offset.offset}${html[offset.offset]}${offset.offset + 1}${html[offset.offset+ 1]}`.replace(" ", "␣").replace("\n", "⏎"));
      html = `${html.slice(0, offset.offset)}\n${html.slice(offset.offset + 1)}`;
    }
    if (offset.kind === "#text|" && html[offset.offset - 2] !== "\n" && html[offset.offset - 1] === " " && html[offset.offset] !== "\r" && html[offset.offset] !== "\n") {
        html = `${html.slice(0, offset.offset - 1)}\n${html.slice(offset.offset)}`;
    }
  }
  html = txtHTMLCDataB64d(html);
  return html;
}

// -----------------------------------------------------------------------------
// command - txt-json-flatten @pub

program
  .command("txt-json-flatten")
  .description("txt-json-flatten description")
  .addOption(new commander.Option("    --width <number>").default(80).argParser(myParseIntPort))
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { width: number, ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    if (opts.ZTest) {
      const json = {
        "j": { "a": "b", "c": "d", "e": "f" },
        "k": [1, true, null]
      };
      assert.strictEqual(`${txtJsonFlat("", json, { width: 1 }).join("\n")}\n`, `\
.j.a: "b"
.j.c: "d"
.j.e: "f"
.k[0]: 1
.k[1]: true
.k[2]: null
`);
      assert.strictEqual(`${txtJsonFlat("", json, { width: 16 }).join("\n")}\n`, `\
.j.a: "b"
.j.c: "d"
.j.e: "f"
.k[0]: 1
.k[1]: true
.k[2]: null
`);
      assert.strictEqual(`${txtJsonFlat("", json, { width: 17 }).join("\n")}\n`, `\
.j.a: "b"
.j.c: "d"
.j.e: "f"
.k: [1,true,null]
`);
      assert.strictEqual(`${txtJsonFlat("", json, { width: 28 }).join("\n")}\n`, `\
.j.a: "b"
.j.c: "d"
.j.e: "f"
.k: [1,true,null]
`);
      assert.strictEqual(`${txtJsonFlat("", json, { width: 29 }).join("\n")}\n`, `\
.j: {"a":"b","c":"d","e":"f"}
.k: [1,true,null]
`);
      assert.strictEqual(`${txtJsonFlat("", json, { width: 48 }).join("\n")}\n`, `\
.j: {"a":"b","c":"d","e":"f"}
.k: [1,true,null]
`);
      assert.strictEqual(`${txtJsonFlat("", json, { width: 49 }).join("\n")}\n`, `\
{"j":{"a":"b","c":"d","e":"f"},"k":[1,true,null]}
`);
      return cliCommandExit(0);
    }
    const flat = txtJsonFlat("", JSON.parse(fs.readFileSync(file ?? "/dev/stdin", "utf8")), { width: opts.width });
    process.stdout.write(`${flat.join("\n")}\n`);
    return cliCommandExit(0);
  });

function txtJsonFlat(key: string, j: unknown, opts: { width: number }): string[] {
  const s = JSON.stringify(j);
  if (typeof j === "string" || typeof j === "number" || j === false || j === true || j === null) {
    return key === "" ? [s] : [`${key}: ${s}`];
  }
  {
    const ks = key === "" ? s : `${key}: ${s}`;
    if (ks.length <= opts.width) {
      return [ks];
    }
  }
  if (Array.isArray(j)) {
    if (j.length === 0) {
      return key === "" ? ["[]"] : [`${key}: []`];
    }
    return [...j.entries()].map(([i, value]) => txtJsonFlat(`${key}[${i}]`, value, opts)).flat();
  }
  assert.ok(isObject(j));
  if (Object.keys(j).length === 0) {
    return key === "" ? ["{}"] : [`${key}: {}`];
  }
  // return Object.entries(j).map(([key, value]) => `.${key}: ${txtJsonFlat(value, {width: opts.width - key.length - 3 /* .:SPACE */})}`);
  return Object.entries(j).map(([thisKey, value]) => txtJsonFlat(`${key}.${thisKey}`, value, opts)).flat();
}

// -----------------------------------------------------------------------------
// command - txt-markdown-cat @pub
// [@cat](file://PATH) -> <PATH content>
// [@cat:@beg:SECTION](file://PATH) -> <PATH: @beg:SECTION...@end:SECTION>
// [@cat:@sec:SECTION](file://PATH) -> <PATH: ## ... @sec:SECTION ...>

program
  .command("txt-markdown-cat")
  .description("txt-markdown-cat description")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    process.stdout.write(txtMarkdownCat(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
    return cliCommandExit(0);
  });

function txtMarkdownCat(txt: string): string {
  while ((reArr = /\[@cat]\(file:\/\/(?<path>[^)]+)\)/.exec(txt)) !== null) {
    const { path } = reArr.groups as { path: string };
    txt = txt.replace(reArr[0], regExpReplacerEscape(stringRemoveLastLine(fs.readFileSync(path, "utf8"))));
  }

  // 0 [@cat:@beg:SECTION](file://PATH) -> <PATH: @beg:SECTION...@end:SECTION>
  while ((reArr = /\[@cat:@beg:(\w+)]\(file:\/\/(.+?)\)/.exec(txt)) !== null) {
    const content = sh(`c.bash be ${reArr[1]} ${reArr[2]}`);
    txt = txt.replace(reArr[0], regExpReplacerEscape(content.replace(/\r?\n$/, "")));
  }

  // 0 [@cat:@sec:SECTION](file://PATH) -> <PATH: ## ... @sec:SECTION ...>
  while ((reArr = /\[@cat:@sec:(\w+)]\(file:\/\/(.+?)\)/.exec(txt)) !== null) {
    const re = new RegExp(`^## .*@sec:${reArr[1]}.*(\\r?\\n){1,2}(?<body>[\\s\\S]+?)(\\r?\\n){1,2}## `, "m");
    const reArr1 = re.exec(fs.readFileSync(reArr[2], "utf8"));
    if (reArr1 === null) {
      throw new AppError(`section not found; pattern: ${re} (at: ${reArr[0]})`);
    }
    // @ts-ignore
    txt = txt.replace(reArr[0], regExpReplacerEscape(reArr1.groups.body));
  }

  return txt;
}

// -----------------------------------------------------------------------------
// command - txt-markdown-code-b64 @pub

/*
```sh
code
```
-> @__code_block__:YGBgc2gKY29kZQpgYGA=
*/

program
  .command("txt-markdown-code-b64")
  .description("txt-markdown-code-b64 description")
  .addOption(new commander.Option("   ---z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    process.stdout.write(txtMarkdownCodeB64(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
    return cliCommandExit(0);
  });

function txtMarkdownCodeB64(txt: string): string {
  for (const match of txt.matchAll(/^```(\w+)?[\s\S]+?^```$/gm)) {
    txt = txt.replace(match[0], `@__code_block__:${Buffer.from(match[0]).toString("base64")}`);
  }
  return txt;
}

// -----------------------------------------------------------------------------
// command - txt-markdown-code-b64d @pub

program
  .command("txt-markdown-code-b64d")
  .description("txt-markdown-code-b64d description")
  .addOption(new commander.Option("   ---z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    process.stdout.write(txtMarkdownCodeB64d(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
    return cliCommandExit(0);
  });

function txtMarkdownCodeB64d(txt: string): string {
  for (const match of txt.matchAll(/^@__code_block__:(.+)$/gm)) {
    txt = txt.replace(match[0], regExpReplacerEscape(Buffer.from(match[1], "base64").toString("utf8")));
  }
  return txt;
}

// -----------------------------------------------------------------------------
// command - txt-markdown-h2-sec @pub

program
  .command("txt-markdown-h2-sec")
  .description("txt-markdown-h2-sec description")
  .addOption(new commander.Option("   ---z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("<section>", "## @sec:<section>"))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (section: string, file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    if (opts.ZTest) {
      section = "SEC";
      file = `${DIR_TMP}/test-txt-markdown-h2-sec.txt`;
      fs.writeFileSync(file, txtMarkdownH2SecTestIn);
    }
    let txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    txt = txtMarkdownCodeB64(txt);
    const matches = [...txt.matchAll(new RegExp(`(?<=(^|\\r?\\n))(?<txt>## .*@sec:${section}\\b[\\s\\S]+?)(?=\r?\n## |\\$)`, "g"))];
    txt = matches.map((match) => match.groups?.txt).join("\n");
    txt = txtMarkdownCodeB64d(txt);
    if (opts.ZTest) {
      assert.strictEqual(txt, txtMarkdownH2SecTestOut);
      return cliCommandExit(0);
    }
    process.stdout.write(txt);
    return cliCommandExit(0);
  });

const txtMarkdownH2SecTestIn = `\
## hi @sec:SEC there

\`\`\`
## code block
\`\`\`

## remove-me-section 1

remove-me-body 1

## @sec:SEC z

aaa

## remove-me-section 2

remove-me-body 2

## a @sec:SEC

EOF
`;

const txtMarkdownH2SecTestOut = `\
## hi @sec:SEC there

\`\`\`
## code block
\`\`\`

## @sec:SEC z

aaa

## a @sec:SEC

EOF
`;

// -----------------------------------------------------------------------------
// command - txt-markdown-h2-section-reduce @pub

/*
## z1
## z1 - z2 - z3
## a - b - c - d
## a - z
↓
## z1
### z2
#### z3
## a
### b
#### c
##### d
### z
*/

program
  .command("txt-markdown-h2-section-reduce")
  .description("txt-markdown-h2-section-reduce description")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const nCommonElementsFromTheBeginning = (arr1: string[], arr2: string[]) => [...arr1, "\0dummy\0"].findIndex((tok, i) => tok !== arr2[i]);
    let tokensStack: string[] = []; // ## z1 - z2 - z3 -> ["z1", "z2", "z3"]
    let txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    txt = txtMarkdownCodeB64(txt);
    let txt2 = "";
    for (const line of txt.split(/\r?\n/)) {
      if (!line.startsWith("## ")) {
        txt2 += `${line}\n`;
        continue;
      }
      const tokens = line.slice("## ".length).split(" - ");
      const nAlreadyPrintedTokens = nCommonElementsFromTheBeginning(tokensStack, tokens);
      for (let level = nAlreadyPrintedTokens; level < tokens.length; level++) {
        txt2 += `##${"#".repeat(level)} ${tokens[level]}\n`;
        if (level !== tokens.length - 1) txt2 += "\n";
      }
      tokensStack = tokens;
    }
    process.stdout.write(txtMarkdownCodeB64d(txt2));
    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - txt-markdown-headers @pub

program
  .command("txt-markdown-headers")
  .description("txt-markdown-headers description")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (file: string | undefined, opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    // without maxBuffer or maxBuffer: 2**21 (2Mi): ENOBUFS
    // 2**26: 64Mi
    const json = JSON.parse(child_process.execSync(`/home/linuxbrew/.linuxbrew/bin/pandoc --from=commonmark+sourcepos --to=json`, { encoding: "utf8", input: txt, maxBuffer: 2 ** 26 }));

    // https://hackage.haskell.org/package/pandoc-types/docs/Text-Pandoc-Definition.html
    // data Block
    const Block = (block: any) => {
      const c = block.c;
      switch (block.t) {
        case "Plain": c.forEach(Inline); break; // Plain [Inline]
        case "Para": c.forEach(Inline); break; // Para [Inline]
        case "LineBlock": throw new Error("TODO"); break; // LineBlock [[Inline]]
        case "CodeBlock": break; // CodeBlock Attr Text
        case "RawBlock": break; // RawBlock Format Text
        case "BlockQuote": c.forEach(Block); break; // BlockQuote [Block]
        case "OrderedList": c[1].forEach((x: any) => x.forEach(Block)); break; // OrderedList ListAttributes [[Block]]
        case "BulletList": c.forEach((x: any) => Block); break; // BulletList [[Block]]
        case "DefinitionList": throw new Error("TODO"); break; // DefinitionList [([Inline], [[Block]])]
        case "Header": attrs.push(...c[1][2]); c[2].forEach(Inline); break; // Header Int Attr [Inline]
        case "HorizontalRule": break; // HorizontalRule
        case "Table": throw new Error("TODO"); break; // Table Attr Caption [ColSpec] TableHead [TableBody] TableFoot
        case "Figure": c[2].forEach(Block);; break; // Figure Attr Caption [Block]
        case "Div": c[1].forEach(Block); break; // Div Attr [Block]
        default: unreachable();
      }
      return;
    }
    // data Inline
    const Inline = (inline: any) => {
      const c = inline.c;
      switch (inline.t) {
        case "Str": break; // Str Text
        case "Emph": c.forEach(Inline); break; // Emph [Inline]
        case "Underline": c.forEach(Inline); break; // Underline [Inline]
        case "Strong": c.forEach(Inline); break; // Strong [Inline]
        case "Strikeout": c.forEach(Inline); break; // Strikeout [Inline]
        case "Superscript": c.forEach(Inline); break; // Superscript [Inline]
        case "Subscript": c.forEach(Inline); break; // Subscript [Inline]
        case "SmallCaps": c.forEach(Inline); break; // SmallCaps [Inline]
        case "Quoted": c[1].forEach(Inline); break; // Quoted QuoteType [Inline]
        case "Cite": c[1].forEach(Inline); break; // Cite [Citation] [Inline]
        case "Code": break; // Code Attr Text
        case "Space": break; // Space
        case "SoftBreak": break; // SoftBreak
        case "LineBreak": break; // LineBreak
        case "Math": throw new Error("TODO"); break; // Math MathType Text
        case "RawInline": break; // RawInline Format Text
        case "Link": c[1].forEach(Inline); break; // Link Attr [Inline] Target
        case "Image": c[1].forEach(Inline); break; // Image Attr [Inline] Target
        case "Note": c.forEach(Block); break; // Note [Block]
        case "Span": c[1].forEach(Inline); break; // Span Attr [Inline]
        default: unreachable();
      }
      return;
    }

    const attrs: [string, string][] = [];
    json.blocks.forEach(Block);
    const lineNums = attrs.filter(([k, v]) => k === "data-pos").map(([k, v]) => v).map((v) => {
      // 0 = "1:1-2:1"
      // 1 = "10:1-11:1"
      // 2 = "22:1-23:1"
      const reArr = /^(\d+):1-(\d+):1$/.exec(v);
      if (reArr === null) throw new Error(`invalid data-pos: ${v}`);
      const line1 = Number.parseInt(reArr[1]);
      const line2 = Number.parseInt(reArr[2]);
      assert.deepStrictEqual(line1 + 1, line2);
      return line1;
    });
    child_process.execSync(`sed -n 1,2p`, { encoding: "utf8", input: txt, maxBuffer: 2 ** 26 });
    child_process.execSync(`sed -n -e ${lineNums.join("p -e ")}p`, { encoding: "utf8", input: txt, maxBuffer: 2 ** 26, stdio: ["pipe", "inherit", "inherit"] });

    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - txt-regexp-search (re) @pub

/*
echo -e "foo\nbar" | c.js -v re -f m '^\w+$'                                     # [["foo"],["bar"]]
echo -e "foo\nbar" | c.js -v re -f m '^((\w)(\w+))$'                             # [["foo","foo","f","oo"],["bar","bar","b","ar"]]
echo -e "foo\nbar" | c.js -v re -f m '^(?<word>(?<head>\w)(?<tail>\w+))$'        # [{"word":"foo","head":"f","tail":"oo"},{"word":"bar","head":"b","tail":"ar"}]
echo -e "foo\nbar" | c.js -v re -f i '^(?<word>(?<head>\w)(?<tail>\w+))$'        # not match with /^(?<word>(?<head>\w)(?<tail>\w+))$/gi

echo -e "foo\nbar" | node -e 'console.log(fs.readFileSync("/dev/stdin", "utf8").match(new RegExp(process.argv[1], "m"))[0]);' '^foo$'
echo -e "foo\nbar" | node -e 'console.log(fs.readFileSync("/dev/stdin", "utf8").match(new RegExp(process.argv[1], process.argv[2] ?? "m"))[0]);' '^foo$' "m"
*/

program
  .command("txt-regexp-search").alias("re")
  .description("txt-regexp-search description")
  .addOption(new commander.Option("-f, --flags <flags>").default("m"))
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .addArgument(new commander.Argument("<pattern>"))
  .addArgument(new commander.Argument("[file]"))
  .allowExcessArguments(false)
  .action(async (pattern: string, file: string | undefined, opts: { flags: string, ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    const re = new RegExp(pattern, opts.flags.includes("g") ? opts.flags : `g${opts.flags}`);
    const matches = [...txt.matchAll(re)];
    if (matches.length === 0) {
      logger.info(`not match with ${re}`);
      return cliCommandExit(1);
    }
    const matchesObj = matches.map((match) => {
      if (match.groups === undefined) return [...match];
      return match.groups;
      // ({ ...[...match], ...match.groups }) // { 0: match[0], 1: match[1], ..., ...match.groups }
    });
    process.stdout.write(`${JSON.stringify(matchesObj)}\n`);
    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - z-meta-command-list @pub

program
  .command("z-meta-command-list")
  .description("meta command - list subcommands")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .allowExcessArguments(false)
  .action(async (opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();
    const names = program.commands.map((command) => command.name());
    process.stdout.write(`${names.join("\n")}\n`);
    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// command - z-meta-publish-self @pub

program
  .command("z-meta-publish-self")
  .description("meta command - publish self")
  .addOption(new commander.Option("   ---z-test").hideHelp().default(false))
  .allowExcessArguments(false)
  .action(async (opts: { ZTest: boolean }) => {
    const optsGlobal = cliCommandInit();

    let match: RegExpMatchArray | null;

    const txtJs = fs.readFileSync(__filename, "utf8");
    // //# sourceMappingURL=data:application/json;base64,<base64>
    match = txtJs.match(/^\/\/# sourceMappingURL=data:application\/json;base64,([\w=]+)$/m);
    if (match === null) throw new AppError(`${__filename}: source map not found`);
    const sourceMap = JSON.parse(Buffer.from(match[1], "base64").toString("utf8"));
    if (sourceMap.sources.length !== 1) throw new AppError(`${__filename}: source map.sources.length !== 1; ${sourceMap.sources}`);
    const tsPath = path.resolve(path.dirname(__filename), sourceMap.sources[0]);
    const txtTs = fs.readFileSync(tsPath, "utf8");

    let pub = true;
    const blocks = txtTs.split("\n// -----------------------------------------------------------------------------\n");
    for (let [i, block] of blocks.entries()) {
      if (block.match(/^(\/\/ command - .+)(\r?\n)/)) {
        if (!RegExp.$1.endsWith("@pub")) {
          continue;
        }
      }
      while ((reArr = /^.*@(pl)\b.*(\r?\n|$)/m.exec(block)) !== null) {
        block = block.replace(reArr[0], "");
      }
      if (i !== 0) {
        process.stdout.write("\n// -----------------------------------------------------------------------------\n");
      }
      process.stdout.write(block);
    }

    return cliCommandExit(0);
  });

// -----------------------------------------------------------------------------
// main

// https://stackoverflow.com/a/60309682/4085441
if (esMain(import.meta)) {
  await cliMain();
  unreachable();
}
