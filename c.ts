#!/usr/bin/env node
// SPDX-FileCopyrightText: Copyright (c) 2021-2025 Wataru Ashihara <wataash0607@gmail.com>
// SPDX-License-Identifier: Apache-2.0
// for WebStorm:
// noinspection RegExpRepeatedSpace

/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/no-unused-expressions */
/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable no-constant-condition */
/* eslint-disable no-debugger */
/* eslint-disable no-regex-spaces */

/*
add newcmd:
fn() { { c.js -q z-meta-command-list; echo "$1"; } | sort | grep -C9999 --color "$1"; }; fn newcmd
bash -c 'fn() { { c.js -q z-meta-command-list; echo "$1"; } | sort | grep -C9999 --color "$1"; }; fn newcmd'
*/

import * as assert from "node:assert/strict";
import * as child_process from "node:child_process";
import * as cp from "node:child_process";
import * as crypto from "node:crypto";
import * as dns from "node:dns";
import * as fs from "node:fs";
import * as fsPromise from "node:fs/promises";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";
import * as readline from "node:readline/promises";
import * as repl from "node:repl";
import * as stream from "node:stream";
import * as tty from "node:tty";
import * as url from "node:url";
import * as util from "node:util";

import * as commander from "@commander-js/extra-typings";
import envPaths from "env-paths";
import esMain from "es-main";
import type express from "express";
import type pty_ from "node-pty";
import fetchSync from "sync-fetch";
const fetchSync_ = fetchSync; // avoid unused-removal
import * as tmp from "tmp";

import { Logger } from "./logger.js";

const __filename = url.fileURLToPath(import.meta.url);
const progname = path.basename(__filename);
export const logger = new Logger();
export const program = new commander.Command();

// -----------------------------------------------------------------------------
// lib

export class AppError extends Error {}

export const DIR_CACHE = envPaths(path.join("wataash", "c.ts")).cache;
export const DIR_TMP = envPaths(path.join("wataash", "c.ts")).temp;
fs.mkdirSync(DIR_CACHE, { recursive: true });
fs.mkdirSync(DIR_TMP, { recursive: true });

/**
 * breakpoint
 */
export function bp(): void {
  return;
}

// https://github.com/nodejs/node/blob/v18.12.1/lib/child_process.js#L861
// Copyright Joyent, Inc. and other Node contributors.
// prettier-ignore
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error
function child_process_checkExecSyncError(ret, args, cmd) {
  let err;
  if (ret.error) {
    // I guess this is set by SetError()
    // https://github.com/nodejs/node/blob/v18.12.1/src/spawn_sync.cc
    // , almost never reached
    err = ret.error;
    Object.assign(err, ret);
  } else if (ret.status !== 0) {
    let msg = 'Command failed: ';
    msg += cmd || args.join(args, ' ');
    if (ret.stderr && ret.stderr.length > 0)
      msg += `\n${ret.stderr.toString()}`;
    err = new Error(msg, ret);
  }
  return err;
}

// Copyright Joyent, Inc. and other Node contributors.
// prettier-ignore
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error
function child_process_checkExecSyncErrorThrow(ret, args, cmd) {
  const err = child_process_checkExecSyncError(ret, args, cmd);
  if (err)
    throw err;
}

/**
 * util.inspect(), maybe with colors (with respect to stderr)
 */
export function ie(object: any): ReturnType<typeof util.inspect> {
  return util.inspect(object, { colors: streamShouldColorize(process.stderr) });
}

/**
 * util.inspect(), maybe with colors (with respect to stdout)
 */
export function io(object: any): ReturnType<typeof util.inspect> {
  return util.inspect(object, { colors: streamShouldColorize(process.stdout) });
}

/**
 * util.inspect(), maybe with colors (with respect to stderr), with infinity width (no line break)
 */
export function iie(object: any): ReturnType<typeof util.inspect> {
  return util.inspect(object, { colors: streamShouldColorize(process.stderr), breakLength: Infinity });
}

/**
 * util.inspect(), maybe with colors (with respect to stdout), with infinity width (no line break)
 */
export function iio(object: any): ReturnType<typeof util.inspect> {
  return util.inspect(object, { colors: streamShouldColorize(process.stdout), breakLength: Infinity });
}

/**
 * integersSummary([]); // []
 * integersSummary([0]); // ["0"]
 * integersSummary([0, 1]); // ["0", "1"]
 * integersSummary([0, 1, 2]); // ["0-2"]
 * integersSummary([0, 1, 2, 4]); // ["0-2", "4"]
 * integersSummary([0, 1, 2, 4, 6]); // ["0-2", "4", "6"]
 * integersSummary([0, 1, 2, 4, 6, 7]); // ["0-2", "4", "6", "7"]
 * integersSummary([0, 1, 2, 4, 6, 7, 8]); // ["0-2", "4", "6-8"]
 * integersSummary([0, 0]); // throws
 * integersSummary([1, 0]); // throws (must be sorted)
 * @param numbers
 */
export function integersSummary(numbers: number[]): string[] {
  if (numbers.length === 0) return [];
  // if (numbers.length === 1) return `${numbers[0]}`;
  const ret = [];
  let begin = numbers[0];
  let prev = numbers[0];
  for (const i of [...numbers.slice(1), 0x7fffffff]) {
    if (prev >= i) throw new Error(`prev:${prev}, i:${i}`);
    if (prev + 1 === i) {
      prev = i;
      continue;
    }
    if (begin === prev) {
      ret.push(`${begin}`);
    } else if (begin + 1 === prev) {
      ret.push(`${begin}`)
      ret.push(`${prev}`)
    } else {
      ret.push(`${begin}-${prev}`);
    }
    begin = prev = i;
  }
  return ret;
}

// https://github.com/jonschlinkert/isobject/blob/master/index.js
export function isObject(value: unknown): value is object {
  return value !== null && typeof value === "object" && Array.isArray(value) === false;
}

export function jsonParsePath(path: string): ReturnType<typeof JSON.parse> {
  try {
    return JSON.parse(fs.readFileSync(path, "utf8"));
  } catch (e) {
    if (!(e instanceof SyntaxError)) throw e;
    e.message = `invalid JSON: ${path}: ${e.message}`;
    throw e;
  }
}
if (0) {
  jsonParsePath(`/etc/hosts`);
  unreachable();
}

export class Queue<T> {
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

let re;
let reArrNull: RegExpExecArray | null;
let reArr_: RegExpExecArray;
let reArr: RegExpExecArray | null; // @depracated
let reArr2: RegExpExecArray; // @depracated

// @deprecated use strEscapeRe()
export function regExpEscape(s: string): string {
  return strEscapeRe(s);
}

export function reExec(regexp: RegExp, string: string): RegExpExecArray | string {
  const reArr = regexp.exec(string);
  if (reArr !== null) return reArr;
  let regexpPartSource = regexp.source;
  let matchedPart;
  while (true) {
    regexpPartSource = regexpPartSource.slice(0, -1);
    try {
      const regexpPart = new RegExp(regexpPartSource, regexp.flags);
      const reArr2 = regexpPart.exec(string);
      if (reArr2 === null)
        continue;
      matchedPart = reArr2[0];
      break;
    } catch (e) {
      // SyntaxError: Invalid regular expression: ...
      if (!(e instanceof SyntaxError)) throw e;
      continue;
    }
    // unreachable();
  }
  const ret = `not matched:
${regexp}
${" ".repeat(`${regexpPartSource}`.length)}^ matched until here (${strSnip(matchedPart, 50)})
(input string: ${strSnip(string, 50)})`;
  // console.log(ret);
  return ret;
}

if (0) {
  assert.equal(reExec(/^(foo)(?<b>bar)x(x)x/, "foobarbaz"), `not matched:
/^(foo)(?<b>bar)x(x)x/
               ^ matched until here (foobar)
(input string: foobarbaz)`);
  assert.equal(reExec(/^(foo)(?<b>bar)x(x)x/gm, "foobarbaz"), `not matched:
/^(foo)(?<b>bar)x(x)x/gm
               ^ matched until here (foobar)
(input string: foobarbaz)`);
  assert.equal(reExec(new RegExp(String.raw`^(foo)(?<b>bar)x/x/x`), "foobarbaz"), `not matched:
/^(foo)(?<b>bar)x\\/x\\/x/
               ^ matched until here (foobar)
(input string: foobarbaz)`);
  assert.equal(reExec(new RegExp(String.raw`^(foo)(?<b>bar)x/x/x`, "gm"), "foobarbaz"), `not matched:
/^(foo)(?<b>bar)x\\/x\\/x/gm
               ^ matched until here (foobar)
(input string: foobarbaz)`);
}

export function reExecThrowAppError(regexp: RegExp, string: string): RegExpExecArray {
  const reArr = reExec(regexp, string);
  if (Array.isArray(reArr)) return reArr;
  throw new AppError(reArr);
}

/**
 * Do String.prototype.replace() without special replacement patterns (e.g. "$1")
 * https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace
 */
export function reReplace(regexp: RegExp, searchValue: string | RegExp, replaceValue: string): RegExp {
  return new RegExp(strReplace(regexp.source, searchValue, replaceValue), regexp.flags);
}

export function reReplaceAll(regexp: RegExp, searchValue: string | RegExp, replaceValue: string): RegExp {
  return new RegExp(strReplaceAll(regexp.source, searchValue, replaceValue), regexp.flags);
}

/**
 * Do String.prototype.replace() with special replacement patterns (e.g. "$1")
 * https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace
 */
export function reReplaceWithSpecial$(regexp: RegExp, searchValue: string | RegExp, replaceValue: string): RegExp {
  return new RegExp(regexp.source.replace(searchValue, replaceValue), regexp.flags);
}

if (0) {
  reReplace(/foo/, /(f)/, "$1"); // /$1oo/
  reReplaceWithSpecial$(/foo/, /(f)/, "$1"); // /foo/
}

/**
 * @deprecated use strReplace
 */
export function regExpReplacerEscape(replacerString: string): string {
  return replacerString.replaceAll("$", "$$$$");
}

// c.js aTemplate --z-dangerous-eval 'child_process.execSync(`NODE_OPTIONS=--inspect-wait c.js aTemplate`, { stdio: ["pipe", "inherit", "inherit"] })'
// c.js aTemplate --z-dangerous-eval 'child_process.execSync(`NODE_OPTIONS=--inspect-wait c.js aTemplate`, { input: "xxx" })'
// echo xxx | c.js aTemplate --z-dangerous-eval 'child_process.execSync(`NODE_OPTIONS=--inspect-wait c.js aTemplate`, { stdio: "inherit" })'
async function readStdin(): Promise<string> {
  if (0) {
    return fs.readFileSync(`/dev/stdin`, "utf8");
    // on Linux, this throws ENXIO when executed from child_process with fd0:pipe:
    //
    // c.js aTemplate --z-dangerous-eval 'child_process.execSync(`c.js aTemplate`, { stdio: ["pipe", "inherit", "inherit"] })'
    // -> readStdin()
    // -> fs.readFileSync(`/dev/stdin`, "utf8")
    // Error: ENXIO: no such device or address, open '/dev/stdin'
    //
    // I guess it's because /dev/stdin is a unix socket (not a pipe!):
    // child_process.execSync(`lsof -nP -p ${process.pid}`, { stdio: "inherit" });
    // COMMAND PID USER   FD      TYPE             DEVICE  SIZE/OFF     NODE NAME
    // node     42  wsh    0u     unix 0x0000000000000000       0t0 17537637 type=STREAM (CONNECTED)
    // node     42  wsh    1u      CHR             136,51       0t0       54 /dev/pts/51
    // node     42  wsh    2u      CHR             136,51       0t0       54 /dev/pts/51
  }

  const decoder = new TextDecoder();
  let s = "";
  for await (const chunk of process.stdin) {
    s += decoder.decode(chunk, { stream: true });
  }
  return s;
}

// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Set/intersection
// https://qiita.com/toshihikoyanase/items/7b07ca6a94eb72164257
/*
Set.prototype.intersection = function(setB) {
  var intersection = new Set();
  // @ts-expect-error
  for (var elem of setB) {
    if (this.has(elem)) {
      intersection.add(elem);
    }
  }
  return intersection;
}
*/

export function sh(cmd: string): string {
  logger.debug(cmd);
  return child_process.execSync(cmd, { encoding: "utf8" });
}

export async function sleep(milliSeconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliSeconds));
}

export async function sleepForever(): Promise<never> {
  while (true) {
    // wakeup every 1 second so that debugger can break here
    // eslint-disable-next-line no-await-in-loop
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

export function strColsWhichAre(s: string, c: string, opts?: { ignoreToTheRightOfShortLine: boolean }): number[] {
  // TODO: full width characters

  if (c.length !== 1) {
    throw new Error(`c.length:${c.length} !== 1 (c: ${c})`);
  }

  s = s.replace(/(\r?\n)$/, "");
  const maxLen = Math.max(...s.split(/\r?\n/).map((line) => line.length));

  let ret: Set<number> = new Set();
  for (let [iLine, line] of s.split(/\r?\n/).entries()) {
    const cols: Set<number> = new Set();
    if (opts?.ignoreToTheRightOfShortLine && line.length < maxLen) {
      line = line.padEnd(maxLen, c);
    }
    for (const match of line.matchAll(/ /dg)) {
      assert.ok(match.indices !== undefined);
      for (const [colStart, colEnd] of match.indices) {
        assert.ok(colStart + 1 === colEnd);
        cols.add(colStart);
      }
    }
    if ((iLine) === 0) {
      ret = cols;
    } else {
      ret = ret.intersection(cols);
    }
  }
  return [...ret].sort((a, b) => a - b);
}

if (0) {
  const tcase = `\
0         1         2         3         4         5         6         7         8
012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789
    ↓↓↓↓↓   ↓   ↓  ↓             ↓  ↓↓↓↓↓↓↓↓↓↓    ↓↓↓↓    ↓↓↓↓    ↓↓↓↓↓   ↓
USER                      STARTED TT          PPID    SESS    PGID     PID CMD
root     Sun Aug 11 11:17:10 2024 ?              0       0       0       2 [kthreadd]
root     Sun Aug 11 11:17:10 2024 ?              2       0       0       3   [rcu_gp]
root     Sun Aug 11 11:17:10 2024 ?              2       0       0       4   [rcu_par_gp]
                    short_line
`.split(/r?\n/).slice(3).join("\n");
  assert.deepEqual(strColsWhichAre(tcase, " "), [4, 5, 6, 7, 8, 12, 16, 19]);
  assert.deepEqual(strColsWhichAre(tcase, " ", { ignoreToTheRightOfShortLine: true }), [4, 5, 6, 7, 8, 12, 16, 19, 33, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 50, 51, 52, 53, 58, 59, 60, 61, 66, 67, 68, 69, 70, 74]);
}

// `sh -c ${strCommandsToShC(["echo", "foo bar"])}`
//
// bash -c 'echo "${@@Q}"' _ echo "foo bar"            # 'echo' 'foo bar'
// bash -c 'echo "${@@Q}"' _ echo ">" "foo bar"        # 'echo' '>' 'foo bar'
// bash -c 'echo "${@@Q}"' _ "echo 'foo bar' > a.txt"  # 'echo '\''foo bar'\'' > a.txt'
//
// a.js echo "foo bar"           # ["echo", "foo bar"]         -> `'echo' 'foo bar'`
// a.js echo ">" "foo bar"       # ["echo", ">", "foo bar"]    -> `'echo' '>' 'foo bar'`
// a.js "echo 'foo bar' > a.txt" # ["echo 'foo bar' > a.txt"]  -> `'echo '\\''foo bar'\\'' > a.txt'`
export function strCommandsToShC(cmds: string[]): string {
  // TODO: implement in js
  const stdout = child_process.execFileSync("bash", ["-c", 'echo "${@@Q}"', "_", ...cmds], { encoding: "utf8" });
  return stdout.trimEnd();
}

// assert.deepStrictEqual(strCommandsToShC(["echo", "foo bar"]), `'echo' 'foo bar'`);
// assert.deepStrictEqual(strCommandsToShC(["echo", ">", "foo bar"]), `'echo' '>' 'foo bar'`);
// assert.deepStrictEqual(strCommandsToShC(["echo 'foo bar' > a.txt"]), `'echo '\\''foo bar'\\'' > a.txt'`);

// strEmptify("\n a \r\n b \n") // -> "\n\r\n\n"
export function strEmptify(s: string): string {
  const matches = s.match(/\r?\n/g); // ES2020: .matchAll()
  if (matches === null) return "";
  return matches.join("");
}

// "|\n a \r\n b \n" 0  strEmptifyFromIndex("\n a \r\n b \n", 0) // \n\r\n\n
// "\n| a \r\n b \n" 1  strEmptifyFromIndex("\n a \r\n b \n", 1) // same
// "\n |a \r\n b \n" 2  strEmptifyFromIndex("\n a \r\n b \n", 2) // \n \r\n\n
// "\n a| \r\n b \n" 3  strEmptifyFromIndex("\n a \r\n b \n", 3) // \n a\r\n\n
// "\n a |\r\n b \n" 4  strEmptifyFromIndex("\n a \r\n b \n", 4) // \n a \r\n\n
// "\n a \r|\n b \n" 5  strEmptifyFromIndex("\n a \r\n b \n", 5) // same
// "\n a \r\n| b \n" 6  strEmptifyFromIndex("\n a \r\n b \n", 6) // same
// "\n a \r\n |b \n" 7  strEmptifyFromIndex("\n a \r\n b \n", 7) // \n a \r\n \n
// "\n a \r\n b| \n" 8  strEmptifyFromIndex("\n a \r\n b \n", 8) // \n a \r\n b\n
// "\n a \r\n b |\n" 9  strEmptifyFromIndex("\n a \r\n b \n", 9) // \n a \r\n b \n
// "\n a \r\n b \n|" 10 strEmptifyFromIndex("\n a \r\n b \n", 10) // \n a \r\n b \n
export function strEmptifyFromIndex(s: string, index: number): string {
  return s.slice(0, index) + strEmptify(s.slice(index));
}

// "|\n a \r\n b \n" 0  strEmptifyUntilIndex("\n a \r\n b \n", 0) // \n a \r\n b \n
// "\n| a \r\n b \n" 1  strEmptifyUntilIndex("\n a \r\n b \n", 1) // same
// "\n |a \r\n b \n" 2  strEmptifyUntilIndex("\n a \r\n b \n", 2) // \na \r\n b \n
// "\n a| \r\n b \n" 3  strEmptifyUntilIndex("\n a \r\n b \n", 3) // \n \r\n b \n
// "\n a |\r\n b \n" 4  strEmptifyUntilIndex("\n a \r\n b \n", 4) // \n\r\n b \n
// "\n a \r|\n b \n" 5  strEmptifyUntilIndex("\n a \r\n b \n", 5) // \n\n b \n    ! \r\n -> \r
// "\n a \r\n| b \n" 6  strEmptifyUntilIndex("\n a \r\n b \n", 6) // \n\r\n b \n
// "\n a \r\n |b \n" 7  strEmptifyUntilIndex("\n a \r\n b \n", 7) // \n\r\nb \n
// "\n a \r\n b| \n" 8  strEmptifyUntilIndex("\n a \r\n b \n", 8) // \n\r\n \n
// "\n a \r\n b |\n" 9  strEmptifyUntilIndex("\n a \r\n b \n", 9) // \n\r\n\n
// "\n a \r\n b \n|" 10 strEmptifyUntilIndex("\n a \r\n b \n", 10) // same
export function strEmptifyUntilIndex(s: string, index: number): string {
  return strEmptify(s.slice(0, index)) + s.slice(index);
}

// ]]> -> ]]]]><![CDATA[>
export function strEscapeCdata(str: string): string {
  // return str.replaceAll("]]>", "]]]]><![CDATA[>"); // es2021
  return str.replace(/]]>/g, "]]]]><![CDATA[>");
}

// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions
export function strEscapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // $& means the whole matched string
}

// https://stackoverflow.com/questions/1779858/how-do-i-escape-a-string-for-a-shell-command-in-node
export function strEscapeShell(str: string) {
  return `"${str.replace(/(["'$`\\])/g, "\\$1")}"`;
}

export function strFirstLine(s: string): string {
  return /^(.*)(\r?\n)/.exec(s)?.[1] ?? s;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function _strFirstLineTest(): void {
  assert.deepStrictEqual(strFirstLine(""), "");
  assert.deepStrictEqual(strFirstLine("\r"), "\r");
  assert.deepStrictEqual(strFirstLine("\x01"), "\x01"); // ^A
  assert.deepStrictEqual(strFirstLine("\n"), "");
  assert.deepStrictEqual(strFirstLine("\r\n"), "");
  assert.deepStrictEqual(strFirstLine("\n\r"), "");
  assert.deepStrictEqual(strFirstLine("xxx"), "xxx");
  assert.deepStrictEqual(strFirstLine("xxx\n"), "xxx");
  assert.deepStrictEqual(strFirstLine("xxx\r\n"), "xxx");
  assert.deepStrictEqual(strFirstLine("xxx\n\r"), "xxx");
  assert.deepStrictEqual(strFirstLine("\nyyy"), "");
  assert.deepStrictEqual(strFirstLine("\r\nyyy"), "");
  assert.deepStrictEqual(strFirstLine("xxx\nyyy"), "xxx");
  assert.deepStrictEqual(strFirstLine("xxx\r\nyyy"), "xxx");
}

// ref: https://github.com/tj/commander.js/blob/v12.1.0/lib/command.js
export function strNodeOptionsRemoveInspect(arg: string): string {
  // Remove:
  //  --inspect[=[host:]port]
  //  --inspect-brk[=[host:]port]
  //  --inspect-port=[host:]port
  //  --inspect-publish-uid=stderr,http
  //  --inspect-wait=[host:]port
  //  --inspect=[host:]port
  // ↑ "=" may be [ \t]+

  // --inspect* [host:]port
  for (const match of arg.matchAll(/(?<=^| )--inspect\S* (\d+:)?\d+(?=$| )/g)) { // not tested
    arg = arg.replace(match[0], ``);
  }
  // --inspect-publish-uid stderr,http
  for (const match of arg.matchAll(/(?<=^| )--inspect-publish-uid\S*(stderr|http)(?=$| )/g)) { // not tested
    arg = arg.replace(match[0], ``);
  }
  // --inspect*
  for (const match of arg.matchAll(/(?<=^| )--inspect\S*(?=$| )/g)) {
    arg = arg.replace(match[0], ``);
  }
  return arg;
}

export function strNodeOptionsRemoveInspectEnv(env: typeof process.env): typeof process.env {
  if (env.NODE_OPTIONS === undefined) return env;
  const env_ = { ...env, NODE_OPTIONS: strNodeOptionsRemoveInspect(env.NODE_OPTIONS) };
  return env_;
}
if (0) {
  strNodeOptionsRemoveInspectEnv(process.env);
}

export function strNumberOfLines(s: string): number {
  return (s.match(/\n/g) ?? []).length + 1;
  // return (s.match(/\n/g)?.length ?? 0) + 1;
}

export interface StrParseSSVEntry {
  value: string;
  colStart: number;
  colEnd: number;
  valueTrimmed: string;
  colStartTrimmed: number;
  colEndTrimmed: number;
};

/**
 * Parse space separated values
 */
export function strParseSSV(s: string, opts?: { ignoreToTheRightOfShortLine: boolean }): StrParseSSVEntry[][] {
  // TODO: full width characters

  // ↓       ↓     ↓↓↓↓↓      ↓↓      ↓↓      ↓↓                   ↓ (Number.MAX_SAFE_INTEGER)  colsDelimiter
  // ↓       ↓     ↓          ↓       ↓       ↓                    ↓ (Number.MAX_SAFE_INTEGER)  colsDelimiterReduced
  // USER     TT          PPID    SESS    PGID     PID CMD
  // root     ?              0       0       0       2 [kthreadd]

  let colsDelimiter = [...strColsWhichAre(s, " ", opts), Number.MAX_SAFE_INTEGER];
  if (colsDelimiter[0] !== 0)
    colsDelimiter = [0, ...colsDelimiter];

  const colsDelimiterReduced = [colsDelimiter[0]]; // [0]
  for (let i = 1; i < colsDelimiter.length; i++) {
    if (colsDelimiter[i - 1] + 1 !== colsDelimiter[i])
      colsDelimiterReduced.push(colsDelimiter[i]);
  }

  const ret: { value: string, colStart: number, colEnd: number, valueTrimmed: string, colStartTrimmed: number, colEndTrimmed: number }[][] = [];
  for (const line of s.replace(/(\r?\n)$/, "").split(/\r?\n/)) {
    const retLine: { value: string, colStart: number, colEnd: number, valueTrimmed: string, colStartTrimmed: number, colEndTrimmed: number }[] = [];
    for (let i = 0; i < colsDelimiterReduced.length - 1; i++) {
      const colStart = colsDelimiterReduced[i];
      let colEnd = colsDelimiterReduced[i + 1];
      const value = line.slice(colStart, colEnd);
      if (colEnd === Number.MAX_SAFE_INTEGER) colEnd = colStart + value.length;
      const valueTrimmed = value.trim();
      if (/^ *$/.test(value)) {
        const colStartTrimmed = colStart;
        const colEndTrimmed = colStart;
        retLine.push({ value, colStart, colEnd, valueTrimmed, colStartTrimmed, colEndTrimmed });
      } else {
        const colStartTrimmed = colStart + /^ */.exec(value)![0].length;
        const colEndTrimmed = colEnd - / *$/.exec(value)![0].length;
        retLine.push({ value, colStart, colEnd, valueTrimmed, colStartTrimmed, colEndTrimmed });
      }
    }
    ret.push(retLine);
  }
  return ret;
}

if (0) {
  const tcase = `\
USER     TT          PPID    SESS    PGID     PID CMD
root     ?              0       0       0       2 [kthreadd]
root     ?              2       0       0       3   [rcu_gp]
               short_line
`;

  const expected1 = [
    [
      { value: 'USER', colStart: 0, colEnd: 4, valueTrimmed: 'USER', colStartTrimmed: 0, colEndTrimmed: 4 },
      { value: '     TT', colStart: 4, colEnd: 11, valueTrimmed: 'TT', colStartTrimmed: 9, colEndTrimmed: 11 },
      { value: '          PPID    SESS    PGID     PID CMD', colStart: 11, colEnd: 53, valueTrimmed: 'PPID    SESS    PGID     PID CMD', colStartTrimmed: 21, colEndTrimmed: 53 }
    ],
    [
      { value: 'root', colStart: 0, colEnd: 4, valueTrimmed: 'root', colStartTrimmed: 0, colEndTrimmed: 4 },
      { value: '     ? ', colStart: 4, colEnd: 11, valueTrimmed: '?', colStartTrimmed: 9, colEndTrimmed: 10 },
      { value: '             0       0       0       2 [kthreadd]', colStart: 11, colEnd: 60, valueTrimmed: '0       0       0       2 [kthreadd]', colStartTrimmed: 24, colEndTrimmed: 60 }
    ],
    [
      { value: 'root', colStart: 0, colEnd: 4, valueTrimmed: 'root', colStartTrimmed: 0, colEndTrimmed: 4 },
      { value: '     ? ', colStart: 4, colEnd: 11, valueTrimmed: '?', colStartTrimmed: 9, colEndTrimmed: 10 },
      { value: '             2       0       0       3   [rcu_gp]', colStart: 11, colEnd: 60, valueTrimmed: '2       0       0       3   [rcu_gp]', colStartTrimmed: 24, colEndTrimmed: 60 }
    ],
    [
      { value: '    ', colStart: 0, colEnd: 4, valueTrimmed: '', colStartTrimmed: 0, colEndTrimmed: 0 },
      { value: '       ', colStart: 4, colEnd: 11, valueTrimmed: '', colStartTrimmed: 4, colEndTrimmed: 4 },
      { value: '    short_line', colStart: 11, colEnd: 25, valueTrimmed: 'short_line', colStartTrimmed: 15, colEndTrimmed: 25 }
    ]
  ];
  assert.deepEqual(strParseSSV(tcase).at(0), expected1.at(0));
  assert.deepEqual(strParseSSV(tcase).at(1), expected1.at(1));
  assert.deepEqual(strParseSSV(tcase).at(2), expected1.at(2));
  assert.deepEqual(strParseSSV(tcase).at(3), expected1.at(3));
  assert.deepEqual(strParseSSV(tcase), expected1);

  const expected2 = [
    [
      { value: 'USER', colStart: 0, colEnd: 4, valueTrimmed: 'USER', colStartTrimmed: 0, colEndTrimmed: 4 },
      { value: '     TT', colStart: 4, colEnd: 11, valueTrimmed: 'TT', colStartTrimmed: 9, colEndTrimmed: 11 },
      { value: '          PPID', colStart: 11, colEnd: 25, valueTrimmed: 'PPID', colStartTrimmed: 21, colEndTrimmed: 25 },
      { value: '    SESS', colStart: 25, colEnd: 33, valueTrimmed: 'SESS', colStartTrimmed: 29, colEndTrimmed: 33 },
      { value: '    PGID', colStart: 33, colEnd: 41, valueTrimmed: 'PGID', colStartTrimmed: 37, colEndTrimmed: 41 },
      { value: '     PID', colStart: 41, colEnd: 49, valueTrimmed: 'PID', colStartTrimmed: 46, colEndTrimmed: 49 },
      { value: ' CMD', colStart: 49, colEnd: 53, valueTrimmed: 'CMD', colStartTrimmed: 50, colEndTrimmed: 53 }
    ],
    [
      { value: 'root', colStart: 0, colEnd: 4, valueTrimmed: 'root', colStartTrimmed: 0, colEndTrimmed: 4 },
      { value: '     ? ', colStart: 4, colEnd: 11, valueTrimmed: '?', colStartTrimmed: 9, colEndTrimmed: 10 },
      { value: '             0', colStart: 11, colEnd: 25, valueTrimmed: '0', colStartTrimmed: 24, colEndTrimmed: 25 },
      { value: '       0', colStart: 25, colEnd: 33, valueTrimmed: '0', colStartTrimmed: 32, colEndTrimmed: 33 },
      { value: '       0', colStart: 33, colEnd: 41, valueTrimmed: '0', colStartTrimmed: 40, colEndTrimmed: 41 },
      { value: '       2', colStart: 41, colEnd: 49, valueTrimmed: '2', colStartTrimmed: 48, colEndTrimmed: 49 },
      { value: ' [kthreadd]', colStart: 49, colEnd: 60, valueTrimmed: '[kthreadd]', colStartTrimmed: 50, colEndTrimmed: 60 }
    ],
    [
      { value: 'root', colStart: 0, colEnd: 4, valueTrimmed: 'root', colStartTrimmed: 0, colEndTrimmed: 4 },
      { value: '     ? ', colStart: 4, colEnd: 11, valueTrimmed: '?', colStartTrimmed: 9, colEndTrimmed: 10 },
      { value: '             2', colStart: 11, colEnd: 25, valueTrimmed: '2', colStartTrimmed: 24, colEndTrimmed: 25 },
      { value: '       0', colStart: 25, colEnd: 33, valueTrimmed: '0', colStartTrimmed: 32, colEndTrimmed: 33 },
      { value: '       0', colStart: 33, colEnd: 41, valueTrimmed: '0', colStartTrimmed: 40, colEndTrimmed: 41 },
      { value: '       3', colStart: 41, colEnd: 49, valueTrimmed: '3', colStartTrimmed: 48, colEndTrimmed: 49 },
      { value: '   [rcu_gp]', colStart: 49, colEnd: 60, valueTrimmed: '[rcu_gp]', colStartTrimmed: 52, colEndTrimmed: 60 }
    ],
    [
      { value: '    ', colStart: 0, colEnd: 4, valueTrimmed: '', colStartTrimmed: 0, colEndTrimmed: 0 },
      { value: '       ', colStart: 4, colEnd: 11, valueTrimmed: '', colStartTrimmed: 4, colEndTrimmed: 4 },
      { value: '    short_line', colStart: 11, colEnd: 25, valueTrimmed: 'short_line', colStartTrimmed: 15, colEndTrimmed: 25 },
      { value: '', colStart: 25, colEnd: 33, valueTrimmed: '', colStartTrimmed: 25, colEndTrimmed: 25 },
      { value: '', colStart: 33, colEnd: 41, valueTrimmed: '', colStartTrimmed: 33, colEndTrimmed: 33 },
      { value: '', colStart: 41, colEnd: 49, valueTrimmed: '', colStartTrimmed: 41, colEndTrimmed: 41 },
      { value: '', colStart: 49, colEnd: 49, valueTrimmed: '', colStartTrimmed: 49, colEndTrimmed: 49 }
    ]
  ];
  assert.deepEqual(strParseSSV(tcase, { ignoreToTheRightOfShortLine: true }).at(0), expected2.at(0));
  assert.deepEqual(strParseSSV(tcase, { ignoreToTheRightOfShortLine: true }).at(1), expected2.at(1));
  assert.deepEqual(strParseSSV(tcase, { ignoreToTheRightOfShortLine: true }).at(2), expected2.at(2));
  assert.deepEqual(strParseSSV(tcase, { ignoreToTheRightOfShortLine: true }).at(3), expected2.at(3));
  assert.deepEqual(strParseSSV(tcase, { ignoreToTheRightOfShortLine: true }), expected2);

  const tcaseIndented = `\
  USER     TT          PPID    SESS    PGID     PID CMD
  root     ?              0       0       0       2 [kthreadd]
  root     ?              2       0       0       3   [rcu_gp]
                 short_line
`;
  const expectedIndented2 = [
    [
      { value: '  USER', colStart: 0, colEnd: 6, valueTrimmed: 'USER', colStartTrimmed: 2, colEndTrimmed: 6 },
      { value: '     TT', colStart: 6, colEnd: 13, valueTrimmed: 'TT', colStartTrimmed: 11, colEndTrimmed: 13 },
      { value: '          PPID', colStart: 13, colEnd: 27, valueTrimmed: 'PPID', colStartTrimmed: 23, colEndTrimmed: 27 },
      { value: '    SESS', colStart: 27, colEnd: 35, valueTrimmed: 'SESS', colStartTrimmed: 31, colEndTrimmed: 35 },
      { value: '    PGID', colStart: 35, colEnd: 43, valueTrimmed: 'PGID', colStartTrimmed: 39, colEndTrimmed: 43 },
      { value: '     PID', colStart: 43, colEnd: 51, valueTrimmed: 'PID', colStartTrimmed: 48, colEndTrimmed: 51 },
      { value: ' CMD', colStart: 51, colEnd: 55, valueTrimmed: 'CMD', colStartTrimmed: 52, colEndTrimmed: 55 }
    ],
    [
      { value: '  root', colStart: 0, colEnd: 6, valueTrimmed: 'root', colStartTrimmed: 2, colEndTrimmed: 6 },
      { value: '     ? ', colStart: 6, colEnd: 13, valueTrimmed: '?', colStartTrimmed: 11, colEndTrimmed: 12 },
      { value: '             0', colStart: 13, colEnd: 27, valueTrimmed: '0', colStartTrimmed: 26, colEndTrimmed: 27 },
      { value: '       0', colStart: 27, colEnd: 35, valueTrimmed: '0', colStartTrimmed: 34, colEndTrimmed: 35 },
      { value: '       0', colStart: 35, colEnd: 43, valueTrimmed: '0', colStartTrimmed: 42, colEndTrimmed: 43 },
      { value: '       2', colStart: 43, colEnd: 51, valueTrimmed: '2', colStartTrimmed: 50, colEndTrimmed: 51 },
      { value: ' [kthreadd]', colStart: 51, colEnd: 62, valueTrimmed: '[kthreadd]', colStartTrimmed: 52, colEndTrimmed: 62 }
    ],
    [
      { value: '  root', colStart: 0, colEnd: 6, valueTrimmed: 'root', colStartTrimmed: 2, colEndTrimmed: 6 },
      { value: '     ? ', colStart: 6, colEnd: 13, valueTrimmed: '?', colStartTrimmed: 11, colEndTrimmed: 12 },
      { value: '             2', colStart: 13, colEnd: 27, valueTrimmed: '2', colStartTrimmed: 26, colEndTrimmed: 27 },
      { value: '       0', colStart: 27, colEnd: 35, valueTrimmed: '0', colStartTrimmed: 34, colEndTrimmed: 35 },
      { value: '       0', colStart: 35, colEnd: 43, valueTrimmed: '0', colStartTrimmed: 42, colEndTrimmed: 43 },
      { value: '       3', colStart: 43, colEnd: 51, valueTrimmed: '3', colStartTrimmed: 50, colEndTrimmed: 51 },
      { value: '   [rcu_gp]', colStart: 51, colEnd: 62, valueTrimmed: '[rcu_gp]', colStartTrimmed: 54, colEndTrimmed: 62 }
    ],
    [
      { value: '      ', colStart: 0, colEnd: 6, valueTrimmed: '', colStartTrimmed: 0, colEndTrimmed: 0 },
      { value: '       ', colStart: 6, colEnd: 13, valueTrimmed: '', colStartTrimmed: 6, colEndTrimmed: 6 },
      { value: '    short_line', colStart: 13, colEnd: 27, valueTrimmed: 'short_line', colStartTrimmed: 17, colEndTrimmed: 27 },
      { value: '', colStart: 27, colEnd: 35, valueTrimmed: '', colStartTrimmed: 27, colEndTrimmed: 27 },
      { value: '', colStart: 35, colEnd: 43, valueTrimmed: '', colStartTrimmed: 35, colEndTrimmed: 35 },
      { value: '', colStart: 43, colEnd: 51, valueTrimmed: '', colStartTrimmed: 43, colEndTrimmed: 43 },
      { value: '', colStart: 51, colEnd: 51, valueTrimmed: '', colStartTrimmed: 51, colEndTrimmed: 51 }
    ]
  ];
  assert.deepEqual(strParseSSV(tcaseIndented, { ignoreToTheRightOfShortLine: true }), expectedIndented2);
}

export function strRemoveFirstLine(s: string): string {
  const i = s.indexOf("\n");
  if (i === -1) return "";
  return s.slice(i + 1);
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function _strRemoveFirstLineTest(): void {
  assert.deepStrictEqual(strRemoveFirstLine(""), "");
  assert.deepStrictEqual(strRemoveFirstLine("foo"), "");
  assert.deepStrictEqual(strRemoveFirstLine("foo\n"), "");
  assert.deepStrictEqual(strRemoveFirstLine("foo\r\n"), "");
  assert.deepStrictEqual(strRemoveFirstLine("foo\n\r"), "\r");
  assert.deepStrictEqual(strRemoveFirstLine("\n\n"), "\n");
  assert.deepStrictEqual(strRemoveFirstLine("\r\n\r\n"), "\r\n");
  assert.deepStrictEqual(strRemoveFirstLine("foo\n\nbar\nbaz\n"), "\nbar\nbaz\n");
  assert.deepStrictEqual(strRemoveFirstLine("foo\r\n\r\nbar\r\nbaz\r\n"), "\r\nbar\r\nbaz\r\n");
}

export function strRemoveLastLine(s: string): string {
  return s.replace(/\r?\n$/, "");
}

export function strRemovePrefix(s: string, prefix: string): string {
  return s.replace(new RegExp(`^${regExpEscape(prefix)}`), "");
}

export function strRemoveSuffix(s: string, suffix: string): string {
  return s.replace(new RegExp(`${regExpEscape(suffix)}$`), "");
}

/**
 * String.prototype.replace() without special replacement patterns (e.g. "$1")
 * https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace
 * @example
 *   "foo".replace(/(f)/, "$1"); // "foo"
 *   strReplace("foo", /(f)/, "$1"); // "$1oo"
 */
export function strReplace(s: string, searchValue: string | RegExp, replaceValue: string): string {
  // replaceValue = replaceValue.replace(/\$/g, "$$$$"); // before ES2021
  replaceValue = replaceValue.replaceAll("$", "$$$$"); // ES2021
  return s.replace(searchValue, replaceValue);
}

export function strReplaceAll(s: string, searchValue: string | RegExp, replaceValue: string): string {
  // replaceValue = replaceValue.replace(/\$/g, "$$$$"); // before ES2021
  replaceValue = replaceValue.replaceAll("$", "$$$$"); // ES2021
  return s.replaceAll(searchValue, replaceValue);
}

export function strSnip(s: string, len: number) {
  s = s.replaceAll(/\r?\n/g, "⏎");
  if (s.length <= len) return s;
  len = Math.floor(len / 2);
  return `${s.slice(0, len)} ... ${s.slice(s.length - len)}`;
}

export function strTrimTrailingSlashes(s: string): string {
  while (s.at(-1) === "/") {
    s = s.slice(0, -1);
  }
  return s;
}

export function streamShouldColorize(stream: NodeJS.WriteStream): boolean {
  // https://github.com/nodejs/node/blob/v22.13.0/lib/util.js styleText()
  // https://github.com/nodejs/node/blob/v22.13.0/lib/internal/util/colors.js shouldColorize()
  // @ts-expect-error util.d.ts is wrong
  return util.styleText("reset", "", { stream }) !== "";
}

export function shouldColorizeWithoutUtilStyleText(stream: NodeJS.WriteStream): boolean {
  // https://github.com/nodejs/node/blob/v22.13.0/lib/util.js styleText()
  // https://github.com/nodejs/node/blob/v22.13.0/lib/internal/util/colors.js shouldColorize()
  if (process.env.FORCE_COLOR !== undefined) {
    // https://github.com/nodejs/node/blob/v22.13.0/lib/internal/tty.js getColorDepth()
    if (["", "1", "true", "2", "3"].includes(process.env.FORCE_COLOR)) return true;
    return false; // any string, including: "true", "on", "foo", and even: "0", "false", "off"
  }
  if (!stream.isTTY) return false;
  // I think this is always true
  if (typeof stream.getColorDepth === "function") {
    return stream.getColorDepth() > 2;
  }
  // unreachable?
  return false;
}

export class TextLineDecoder {
  #decoder = new TextDecoder();
  #buf = "";
  decode(input: Parameters<TextDecoder["decode"]>[0]): ReturnType<TextDecoder["decode"]> {
    this.#buf += this.#decoder.decode(input, { stream: true });
    const match = this.#buf.match(/^[\s\S]*\n/);
    if (match === null)
      return "";
    this.#buf = this.#buf.slice(match[0].length);
    return match[0];
  }
}

export function unreachable(): never {
  throw new Error("BUG: unreachable");
}

// -----------------------------------------------------------------------------
// cli

export const VERSION = "0.1.0";

// @ts-expect-error
const cliOptsGlobal: {
  quiet: number;
  zHiddenGlobalOption: boolean;
} = {};

program
  .name("c.js")
  .description("mini CLIs")
  .version(VERSION)
  .addOption(new commander.Option("-q, --quiet", "quiet mode; -q to suppress debug log, -qq to suppress info log, -qqq to suppress warn log, -qqqq to suppress error log").default(0).argParser((_undefined, previous: number) => previous + 1))
  .addOption(new commander.Option("--z-hidden-global-option").hideHelp().default(false))
  .hook("preAction", async (thisCommand, actionCommand) => {
    Object.freeze(Object.assign(cliOptsGlobal, thisCommand.opts()));
    switch (true) {
      case cliOptsGlobal.quiet === 0: logger.level = Logger.Level.Debug; break;
      case cliOptsGlobal.quiet === 1: logger.level = Logger.Level.Info; break;
      case cliOptsGlobal.quiet === 2: logger.level = Logger.Level.Warn; break;
      case cliOptsGlobal.quiet === 3: logger.level = Logger.Level.Error; break;
      case cliOptsGlobal.quiet >= 4: logger.level = Logger.Level.Silent; break;
    }
    logger.debug(`PID ${process.pid}`, process.argv);
  });

const cliCommandExitResolvers  = Promise.withResolvers<number>();
export const cliCommandExit = cliCommandExitResolvers.resolve;

export async function cliMain(): Promise<void> {
  try {
    await program.parseAsync(process.argv);
    process.exitCode = await cliCommandExitResolvers.promise;
    assert.ok(process.exitCode !== undefined);
    return;
  } catch (e) {
    if (!(e instanceof AppError)) {
      logger.error(`unexpected error: ${e}`);
      throw e;
    }
    // assert.ok(e.constructor.name === "AppError")
    logger.error(e.message);
    if (process.exitCode === undefined) {
      process.exitCode = 1;
    }
    return;
  }
  unreachable();
}

const cliCmds: { [cmdName: string]: (...args: any[]) => void | Promise<void> } = {};

// -----------------------------------------------------------------------------
// lib for commands

export class CLI {
  // https://github.com/tj/commander.js#custom-option-processing

  static parseDuration(value: string, dummyPrevious?: number): number {
    if (value.match(/^\d+$/)) return parseInt(value);
    const cmd = `date -d ${strEscapeShell(`19700101 ${value}`)} -u +%s`;
    const secs = parseInt(sh(cmd));
    if (secs < 0) throw new commander.InvalidArgumentError(`value: ${value} < 0 (cmd: ${cmd})`); // e.g. -1sec
    return secs;
  }

  // accept: -2 -1 0 1 2
  static parseInt(value: string, dummyPrevious?: number): number {
    const parsedValue = parseInt(value, 10);
    if (Number.isNaN(parsedValue)) throw new commander.InvalidArgumentError("not a number.");
    return parsedValue;
  }

  // accept:         1 2
  static parseIntPositive(value: string, dummyPrevious?: number): number {
    const parsedValue = parseInt(value, 10);
    if (Number.isNaN(parsedValue)) throw new commander.InvalidArgumentError("not a number.");
    if (parsedValue <= 0) throw new commander.InvalidArgumentError("must be >0.");
    return parsedValue;
  }

  // accept:       0 1 2
  static parseIntPositiveOrZero(value: string, dummyPrevious?: number): number {
    const parsedValue = parseInt(value, 10);
    if (Number.isNaN(parsedValue)) throw new commander.InvalidArgumentError("not a number.");
    if (parsedValue < 0) throw new commander.InvalidArgumentError("must be >=0.");
    return parsedValue;
  }

  // accept:    -1 0 1 2
  static parseIntPositiveOrZeroOrNegativeOne(value: string, dummyPrevious?: number): number {
    const parsedValue = parseInt(value, 10);
    if (Number.isNaN(parsedValue)) throw new commander.InvalidArgumentError("not a number.");
    if (parsedValue < -1) throw new commander.InvalidArgumentError("must be >=0 or -1.");
    return parsedValue;
  }

  // accept: 0-65535
  static parseIntPort(value: string, dummyPrevious?: number): number {
    const parsedValue = parseInt(value, 10);
    if (Number.isNaN(parsedValue)) throw new commander.InvalidArgumentError("not a number.");
    if (parsedValue < 0 || parsedValue > 65535) throw new commander.InvalidArgumentError("must be 0-65535.");
    return parsedValue;
  }
}

// -----------------------------------------------------------------------------
// command - aTemplate (at)
// draft: other template candidates: execGitDiffPatch txtGitDiffPatch

program.command("aTemplate").alias("at").description("aTemplate description")
  .addArgument(new commander.Argument("[file]"))
  .addOption(new commander.Option("-a, --a-opt", "a option").default(false).conflicts(["bOpt"]))
  .addOption(new commander.Option("-b, --b-opt", "b option").default(false).conflicts(["aOpt"]))
  .addOption(new commander.Option("--port <port>", "port number").default(3000).argParser(CLI.parseIntPort))
  .addOption(new commander.Option("--test=<target>").choices(["Error", "AppError", ""]))
  .addOption(new commander.Option("--z-dangerous-eval <code>").hideHelp())
  .action((file, opts) => aTemplate(file, { _cli: true, ...opts }));

async function  aTemplate(
  file: string | undefined,
  opts: {
    _cli?: boolean,
    aOpt: boolean,
    bOpt: boolean,
    port: number,
    zDangerousEval?: string,
  },
) {
  if (opts.zDangerousEval !== undefined) {
    eval(opts.zDangerousEval);
    return cliCommandExit(0);
  }
  const txt = file ? fs.readFileSync(file, "utf8") : await (async () => {
    logger.info(`reading from stdin...`);
    return await readStdin();
  })();
  logger.info(`txt.length: ${txt.length}`);
  return cliCommandExit(0);
}

// NODE_OPTIONS="--enable-source-maps --import @power-assert/node" CTS_TEST_CLI=1 c.js
if (process.env.CTS_TEST_CLI) {
  logger.warn("CTS_TEST_CLI -- c.ts tests for cli (commander.js)");
  const { CTS_TEST_CLI, ...env } = process.env;
  if ("NODE_OPTIONS" in env) {
    // remove --inspect[-*]
    env.NODE_OPTIONS = "";
  }
  let r; // result of child_process.spawnSync()
  let out, err; // previous stdout, stderr

/*
c.js
c.js -qq
c.js -h
c.js -qq -h
*/

  r = child_process.spawnSync(`c.js`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 1 && r.stdout === "" && r.stderr !== "");
  assert.match(r.stderr, /^Usage: c.js /);
  [out, err] = [r.stdout, r.stderr];

  r = child_process.spawnSync(`c.js -qq`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 1 && r.stdout === "" && r.stderr !== "");
  assert.equal(r.stderr, err);
  [out, err] = [r.stdout, r.stderr];

  r = child_process.spawnSync(`c.js -h`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 0 && r.stdout !== "" && r.stderr === "");
  assert.match(r.stdout, /^Usage: c.js /);
  [out, err] = [r.stdout, r.stderr];

  r = child_process.spawnSync(`c.js -qq -h`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 0 && r.stdout !== "" && r.stderr === "");
  assert.equal(r.stdout, out);
  [out, err] = [r.stdout, r.stderr];

/*
c.js     aTemplate /dev/null
c.js -qq aTemplate /dev/null
c.js     aTemplate -h
c.js -qq aTemplate -h
*/

  r = child_process.spawnSync(`c.js     aTemplate /dev/null`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 0 && r.stdout === "" && r.stderr !== "");
  assert.match(r.stderr, /^\d{4}-\d{2}-\d{2} .+ PID \d+ /);
  [out, err] = [r.stdout, r.stderr];

  r = child_process.spawnSync(`c.js -qq aTemplate /dev/null`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 0 && r.stdout === "" && r.stderr === "");
  [out, err] = [r.stdout, r.stderr];

/*
c.js -q aTemplate ---z-dangerous-eval "                       throw new AppError('app err')"  # 1
c.js -q aTemplate ---z-dangerous-eval "process.exitCode = 42; throw new AppError('app err')"  # 42
c.js -q aTemplate ---z-dangerous-eval "                       throw new Error('err')"         # 1
c.js -q aTemplate ---z-dangerous-eval "process.exitCode = 42; throw new Error('err')"         # 1 (exitCode ignored)
*/

  r = child_process.spawnSync(`c.js -q aTemplate ---z-dangerous-eval "                       throw new AppError('app err')"`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 1 && r.stdout === "" && r.stderr !== "");
  assert.match(r.stderr, /^\d{4}-\d{2}-\d{2} .+ app err(\r?\n)$/);
  [out, err] = [r.stdout, r.stderr];

  r = child_process.spawnSync(`c.js -q aTemplate ---z-dangerous-eval "process.exitCode = 42; throw new AppError('app err')"`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 42 && r.stdout === "" && r.stderr !== "");
  assert.match(r.stderr, /^\d{4}-\d{2}-\d{2} .+ app err(\r?\n)$/);
  [out, err] = [r.stdout, r.stderr];

  /*
2006-01-02 15:04:05 [E][cliMain:690] unexpected error: Error: err
undefined:1    ← ??? now shown when using debugger ?!
                       throw new Error('err')
                             ^

Error: err
    at eval (eval at aTemplate (file:///home/wsh/qjs/tesjs/d/c.js:764:9), <anonymous>:1:7)
    at Command.aTemplate (file:///home/wsh/qjs/tesjs/d/c.js:764:9)
    at Command.listener [as _actionHandler] (/home/wsh/qjs/tesjs/node_modules/commander/lib/command.js:542:17)
    at /home/wsh/qjs/tesjs/node_modules/commander/lib/command.js:1502:14
    at /home/wsh/qjs/tesjs/node_modules/commander/lib/command.js:1383:33
    at async Command.parseAsync (/home/wsh/qjs/tesjs/node_modules/commander/lib/command.js:1092:5)
    at async cliMain (file:///home/wsh/qjs/tesjs/d/c.js:684:9)
    at async file:///home/wsh/qjs/tesjs/d/c.js:4469:5

Node.js v22.12.0
*/

  r = child_process.spawnSync(`c.js -qq aTemplate ---z-dangerous-eval "                       throw new Error('err')"`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 1 && r.stdout === "" && r.stderr !== "");
  assert.match(r.stderr, /^\d{4}-\d{2}-\d{2} .+ unexpected error: Error: err(\r?\n)undefined:1(\r?\n) *throw new Error\(/);
  [out, err] = [r.stdout, r.stderr];

  r = child_process.spawnSync(`c.js -qq aTemplate ---z-dangerous-eval "process.exitCode = 42; throw new Error('err')"`, { encoding: "utf8", env, shell: true, stdio: "pipe" });
  assert.ok(r.signal === null && !("error" in r) && r.status === 1 && r.stdout === "" && r.stderr !== "");
  assert.match(r.stderr, /^\d{4}-\d{2}-\d{2} .+ unexpected error: Error: err(\r?\n)undefined:1(\r?\n)process.exitCode = 42; throw new Error\(/);
  [out, err] = [r.stdout, r.stderr];
}

// -----------------------------------------------------------------------------
// command - aTxtParseTemplate

program.command("aTxtParseTemplate").description("aTxtParseTemplate description")
  .addArgument(new commander.Argument("[file]"))
  .action((file, opts) => {
    const txt = fs.readFileSync(file ?? (() => {
      logger.info(`reading from stdin...`);
      return "/dev/stdin";
    })(), "utf8");
    logger.debug(`txt.length: ${txt.length}`);
    process.stdout.write(aTxtParseTemplate(txt));
    return cliCommandExit(0);
  });

function  aTxtParseTemplate(txt: string): string {
  return txt;
}

// -----------------------------------------------------------------------------
// command - cflmd

/*
Works only with Confluence API version 1.
https://developer.atlassian.com/cloud/confluence/rest/v1/

Confluence URL examples:
https://wiki.sei.cmu.edu/confluence/                                        urlConfluenceTop
https://wiki.sei.cmu.edu/confluence/display/c/SEI+CERT+C+Coding+Standard    type: "kt" (speceKey + title)
https://wiki.sei.cmu.edu/confluence/pages/viewpage.action?pageId=87152044   type: "id"

Cache files:
/rest/api/* -> cflmd/api/* (escaped), with "at":epochMilliseconds, "at2":"2006-01-02 15:04:05"
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/api/content/{id}.json                    {"at":1136214845000, "at2":"2006-01-02 15:14:05", "id":87152044, "spaceKey":"c", "title":"SEI CERT C Coding Standard"} // "at" in milliseconds
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/api/content/{id}/child/attachment.json   {"at":1136214845000, "at2":"2006-01-02 15:14:05", "results":[{"id":42,"type":"attachment","status":"current","title":"a.png","metadata":{"mediaType":"image/png","labels":{...}},"_expandable":{...}}, "extensions":{...}, "_links":{...}, "_expandable":{...}}, start:0, limit:50, size:10, _links:{...}}
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/api/content/{spaceKey}/{webuiTitle}      content?spaceKey={spaceKey}&title={webuiTitle}
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/download/attachments/{id}/{filename}?version={version}&modificationDate={modificationDate(epochMilliseconds)}&api=v2
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/download/attachments/{id}/{filename}?version={version}&modificationDate={modificationDate(epochMilliseconds)}&api=v2.json  {"at":1136214845000, "at2":"2006-01-02 15:14:05", "id":42, "type":"attachment", ...} (from attachment.json)
maybe old:
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/0.original.md
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/0_hack.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/0_hack.html.diff
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/1.prep.0_cat.md
...
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/1.prep.zz_code_macro.md
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/1.prep.zz_code_macro.md.diff
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/2.pandoc.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/2.pandoc.html.diff
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/3.postp.link.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/3.postp.link.html.diff
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/3.postp.table.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/3.postp.table.html.diff
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/3.postp.z_macro_id.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/3.postp.z_macro_id.html.diff
TODO: update
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/4.format.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/4.format.html.diff
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/4.format.html.with_title.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/4.format.html.with_title.html.diff
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/remote.0.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/remote.4.format.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/remote.4.format.html.with_title.html
/home/wsh/.cache/wataash/c.ts-nodejs/cflmd/last/remote.4.format.html.with_title.html.diff
*/

program.command("cflmd").description("cflmd description")
  .addOption(new commander.Option("--user <user>", "Confluence user name (required)").env("CFLMD_USER").makeOptionMandatory(true))
  .addOption(new commander.Option("--token <token>", "Confluence API token or password (required)").env("CFLMD_TOKEN").makeOptionMandatory(true))
  .addOption(new commander.Option("--cache-secs-page <number>", "http GET cache seconds for pages").env("CFLMD_CACHE_SECS_PAGE").default(300).argParser(CLI.parseInt))
  .addOption(new commander.Option("--cache-secs-img <number>", "http GET cache seconds for images").env("CFLMD_CACHE_SECS_IMG").default(86400 * 30).argParser(CLI.parseInt))
  .addOption(new commander.Option("--diff-no-macro-id", "diff without ac:macro-id").default(false))
  .addArgument(new commander.Argument("<file>"))
  .addHelpText("afterAll", `
==================================================
file format
==================================================

<!--
[title](https://wiki.sei.cmu.edu/confluence/display/c/SEI+CERT+C+Coding+Standard)
-->

## Section

pandoc markdown goes here...

## Header format

\`\`\`md
<!--
[title](https://wiki.sei.cmu.edu/confluence/display/c/SEI+CERT+C+Coding+Standard)
comment lines
-->
\`\`\`

or:

\`\`\`md
<!--
[title](https://wiki.sei.cmu.edu/confluence/pages/viewpage.action?pageId=87152044)
comment lines
-->
\`\`\`
`)
  .action(cflmd);

async function cflmd(
  file: string,
  opts: {
    user: string,
    token: string,
    cacheSecsPage: number,
    cacheSecsImg: number,
    diffNoMacroId: boolean,
  },
) {
  fs.mkdirSync(`${DIR_CACHE}/cflmd/last/`, { recursive: true });
  // old
  if (0) {
    // TODO: --cache-secs-* が大きい場合不要
    logger.debug(`remove old caches in ${DIR_CACHE}/cflmd/ -- img/ (30 days), last/ (1 hour), pages/ (30 days)`);
    const out = child_process.execSync(`
    find ${DIR_CACHE}/cflmd/img/ -mtime +30 -xtype f -delete -print
    find ${DIR_CACHE}/cflmd/last/ -mmin +60 -xtype f -delete -print
    find ${DIR_CACHE}/cflmd/pages/ -mtime +30 -xtype f -delete -print
  `, { encoding: "utf8" });
    if (out !== "") {
      logger.info(`removed old caches:\n${out}`);
    }
  }

  const txts = [] as { name: string; txt: string }[];

  let txt = fs.readFileSync(file, "utf8");
  cflmdWrite(txts, "0.original.md", txt, false);

  const match = reExecThrowAppError(/^<!--(\r?\n)\[(?<title>[^\]]+)]\((?<url>.+)\)/, txt);
  const { title, url } = match.groups!;
  const cflmdFile: CflmdFile = { path: file, title, url: cflmdParseURL(url) };

  const pagePromise = cflmdPageGet(opts, cflmdFile.url).then((page) => {
    if (cflmdFile.title !== page.title) {
      logger.info(`update title: (${page.title} -> ${cflmdFile.title})`);
    }
    return page;
  });

  txt = await cflmdProcess1MarkdownPreProcess({ file: cflmdFile, opts, pagePromise, txts });
  // cflmdWrite(txt, "1.prep.md", false);

  txt = await cflmdProcess2Pandoc({ file: cflmdFile, opts, pagePromise, txts });
  cflmdWrite(txts, "2.pandoc.html", txt, true);

  txt = await cflmdProcess3HTMLPostProcess({ file: cflmdFile, opts, pagePromise, txts });
  // cflmdWrite(txts, "3.postp.html, txt, ", true);

  // echo 'x <b>x</b>' | minify --html  # x <b>x</b>
  // echo 'x <x>x</x>' | minify --html  # x<x>x</x>
  const { minify } = await import("html-minifier");
  if (0) {
    // collapseWhitespace: true: \n -> space
    minify("a\na", {}); // a\na
    minify("a\na", { collapseWhitespace: true }); // a a
    // <a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK>...</a>
    minify("a\n<a>a</a>", { collapseWhitespace: true }); // a <a>a</a>
    minify("a\n<x>a</x>", { collapseWhitespace: true }); // a<x>a</x> (htmlminifier.js: <x> is not in `var inlineTags`)
    minify("a\n<a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK>a</a>", { collapseWhitespace: true }); // a <a cfmd_hack_no_trim_spaces_around_ac_link>a</a>
    minify("a\n<a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK>a</a>", { caseSensitive: true, collapseWhitespace: true }); // a <a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK>a</a>
  }
  txt = minify(txt, { caseSensitive: true, collapseWhitespace: true, keepClosingSlash: true });
  // <a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK>...</a> -> <ac:link ...>...</ac:link>
  txt = txt.replaceAll(/<a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK>(.+?)<\/a>/g, "<ac:link>$1</ac:link>");

  cflmdWrite(txts, "4.minify.html", txt, true);
  // TODO: assert.ok(dom equal)

  // txt = await cflmdProcess4FormatHtml({ file: cflmdFile, opts, pagePromise, txts });
  // cflmdWrite(txts, "4.format.html", txt, true);
  //
  // txt = `<!--\n[${title}](${url})\n-->\n\n${txt}`;
  // cflmdWrite(txts, "4.format.html.with_title.html", txt, true);

  txt = `title: ${title}\nurl: ${url}\n\n` + txt.replaceAll("><", ">\n<");
  txt = txt.replaceAll(" <ac:link>", "<ac:link>");  // reduce diff with remote.4.minify.html.title.linebreak.maybe_invalid_html.html
  cflmdWrite(txts, "4.minify.html.title.linebreak.maybe_invalid_html.html", txt, true);

  // remote
  {
    const page = await pagePromise;
    let txt = page.body.storage.value;
    cflmdWrite(txts, "remote.0.html", txt, false);

    txt = minify(txt, { caseSensitive: true, collapseWhitespace: true, keepClosingSlash: true });
    cflmdWrite(txts, "remote.4.minify.html", txt, true);
    // TODO: assert.ok(dom equal)

    // if (txt.endsWith("\n")) {
    //   debugger;
    //   logger.warn("reachable? remote ends with NL");
    // } else {
    //   txt += "\n";
    // }

    const url = cflmdFile.url.type === "id" ? `${cflmdFile.url.urlConfluenceTop}/pages/viewpage.action?pageId=${page.id}` : `${cflmdFile.url.urlConfluenceTop}${page._links.webui}`;
    txt = `title: ${title}\nurl: ${url}\n\n` + txt.replaceAll("><", ">\n<");
    txt = txt.replaceAll("&quot;", '"'); // PUT: <p>"a"</p> -> remote: <p>&quot;a&quot;</p>  at the PUT stage, converting " to &quot; is tough (needs HTML-parsing), so only reducing the diff
    cflmdWrite(txts, "remote.4.minify.html.title.linebreak.maybe_invalid_html.html", txt, true);
  }

  // diff
  {
    const out = child_process.execSync(`cmp -s ${DIR_CACHE}/cflmd/last/remote.4.minify.html.title.linebreak.maybe_invalid_html.html ${DIR_CACHE}/cflmd/last/4.minify.html.title.linebreak.maybe_invalid_html.html || echo "differ"`, { encoding: "utf8" });
    if (out === "") {
      logger.info("up-to-date");
      return cliCommandExit(0);
    }
    assert.match(out, /^differ(\r?\n)$/);
  }
  // TODO: --diff-cmd="diff -u" --diff-cmd="delta --paging=never"
  if (opts.diffNoMacroId) {
    fs.writeFileSync(`${DIR_CACHE}/cflmd/last/remote.4.minify.html.title.linebreak.maybe_invalid_html.html.macro_id_0.html`, fs.readFileSync(`${DIR_CACHE}/cflmd/last/remote.4.minify.html.title.linebreak.maybe_invalid_html.html`, "utf8").replace(/ac:macro-id="[^"]+"/g, 'ac:macro-id="0"'));
    fs.writeFileSync(`${DIR_CACHE}/cflmd/last/4.minify.html.title.linebreak.maybe_invalid_html.html.macro_id_0.html`, fs.readFileSync(`${DIR_CACHE}/cflmd/last/4.minify.html.title.linebreak.maybe_invalid_html.html`, "utf8").replace(/ac:macro-id="[^"]+"/g, 'ac:macro-id="0"'));
    child_process.execSync(`delta --paging=never ${DIR_CACHE}/cflmd/last/remote.4.minify.html.title.linebreak.maybe_invalid_html.html.macro_id_0.html ${DIR_CACHE}/cflmd/last/4.minify.html.title.linebreak.maybe_invalid_html.html.macro_id_0.html || true`, { stdio: "inherit" });
  } else {
    child_process.execSync(`delta --paging=never ${DIR_CACHE}/cflmd/last/remote.4.minify.html.title.linebreak.maybe_invalid_html.html ${DIR_CACHE}/cflmd/last/4.minify.html.title.linebreak.maybe_invalid_html.html || true`, { stdio: "inherit" });
  }

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const page = await pagePromise;
  const ans = await rl.question(`update? [y/N] (url: ${cflmdFile.url.urlConfluenceTop}${page._links.webui})`);
  rl.close(); // without this, cannot quit with Ctrl+C
  if (ans.toLowerCase() !== "y" && ans.toLowerCase() !== "yes") {
    logger.warn(`do nothing`);
    return cliCommandExit(1);
  }

  txt = fs.readFileSync(`${DIR_CACHE}/cflmd/last/4.minify.html`, "utf8");
  if (0) {
    //
    txt = `<p>line 1</p>\n<p>line 2</p>\n\n`
    // --PUT-------------> <p>line 1</p>\n<p>line 2</p> (trailing \n removed)
    // --save on web UI--> <p>line 1</p><p>line 2</p>   (minified)
  }
  const pagePut = await cflmdPagePut(opts, cflmdFile, txt, pagePromise);
  logger.info(`updated: ${pagePut.title} (${cflmdFile.url.urlConfluenceTop}${pagePut._links.webui})`);

  return cliCommandExit(0);
}

async function cflmdFetchJSON(url: Parameters<typeof fetch>[0], init: NonNullable<Parameters<typeof fetch>[1]>, opts: {
  logFetch: typeof logger.debug,
  cache?: { type: "rw", path: string, validSecs: number, validSecsOpt: string } | { type: "w", path: string }
}): Promise<any & { at: number, at2: string }> {
  const d = new Date();
  const now = Number(d); // Date.now()
  const now2 = d.toLocaleString("sv-SE");

  const jsonCache = (() => {
    if (opts.cache === undefined) return null;
    if (opts.cache.type !== "rw") return null;
    if (!fs.existsSync(opts.cache.path)) return null;
    const json = jsonParsePath(opts.cache.path);
    if (typeof json.at !== "number") {
      logger.warn(`${opts.cache.path}: invalid cache file: ".at": ${json.at}`);
      return null;
    }
    if (now - json.at > opts.cache.validSecs * 1000) {
      logger.debug(`cache expired: ${opts.cache.path} (${((now - json.at) / 1000).toFixed(1)}s ago > ${opts.cache.validSecs}s) (${opts.cache.validSecsOpt})`);
      return null;
    }
    logger.debug(`use cache: ${opts.cache.path} (${((now - json.at) / 1000).toFixed(1)}s ago <= ${opts.cache.validSecs}s) (${opts.cache.validSecsOpt})`);
    return json;
  })();
  if (jsonCache !== null) {
    return jsonCache;
  }

  opts.logFetch?.(`${init.method} ${url}`);
  const resp = await fetch(url, init);
  const respTxt = await resp.text();
  if (!resp.ok) {
    const statusText = resp.statusText === "401" ? "Unauthorized" : resp.statusText; // why not "Unauthorized"? bug?
    logger.error(`${init.method} ${url}: ${resp.status} ${statusText}`);
    logger.warn(`respTxt: ${respTxt}`);
    throw new AppError(`GET ${url}: ${resp.status} ${statusText}`);
  }
  const json = JSON.parse(respTxt);
  _cflmdFetchJSONCheckJSON(json);
  json.at = now;
  json.at2 = now2;

  if (opts.cache !== undefined) {
    logger.debug(`write cache: ${opts.cache.path}`);
    fs.mkdirSync(path.dirname(opts.cache.path), { recursive: true });
    fs.writeFileSync(opts.cache.path, JSON.stringify(json, null, 2));
  }

  return json;
}

async function cflmdFetchBuffer(url: Parameters<typeof fetch>[0], init: NonNullable<Parameters<typeof fetch>[1]>, opts: {
  logFetch: typeof logger.debug,
  cache?: { type: "rw", path: string, validSecs: number, validSecsOpt: string } | { type: "w", path: string }
}): Promise<Buffer> {
  const d = new Date();
  const now = Number(d); // Date.now()
  const now2 = d.toLocaleString("sv-SE");

  const bufferCache = (() => {
    if (opts.cache === undefined) return null;
    if (opts.cache.type !== "rw") return null;
    if (!fs.existsSync(opts.cache.path)) return null;
    const stat = fs.statSync(opts.cache.path);
    if (now - stat.mtimeMs > opts.cache.validSecs * 1000) {
      logger.debug(`cache expired: ${opts.cache.path} (${((now - stat.mtimeMs) / 1000).toFixed(1)}s ago > ${opts.cache.validSecs}s) (${opts.cache.validSecsOpt})`);
      return null;
    }
    logger.debug(`use cache: ${opts.cache.path} (${((now - stat.mtimeMs) / 1000).toFixed(1)}s ago <= ${opts.cache.validSecs}s) (${opts.cache.validSecsOpt})`);
    const buffer = fs.readFileSync(opts.cache.path);
    return buffer;
  })();
  if (bufferCache !== null) {
    return bufferCache;
  }

  opts.logFetch?.(`${init.method} ${url}`);
  const resp = await fetch(url, init);
  if (!resp.ok) {
    debugger;
    const statusText = resp.statusText === "401" ? "Unauthorized" : resp.statusText; // why not "Unauthorized"? bug?
    logger.error(`${init.method} ${url}: ${resp.status} ${statusText}`);
    const respTxt = await resp.text();
    logger.warn(`respTxt: ${respTxt}`);
    throw new AppError(`GET ${url}: ${resp.status} ${statusText}`);
  }

  const blob = await resp.blob();
  const arrayBuffer = await blob.arrayBuffer();
  if (opts.cache !== undefined) {
    logger.debug(`write cache: ${opts.cache.path}`);
    fs.mkdirSync(path.dirname(opts.cache.path), { recursive: true });
    fs.writeFileSync(opts.cache.path, Buffer.from(arrayBuffer));
  }

  // Return Buffer to match ReturnType<typeof fs.readFileSync>, but if you don't consider it, Blob is the most informative.
  return Buffer.from(arrayBuffer);
  // return blob;
}

function cflmdFetchJSONSync(url: Parameters<typeof fetchSync>[0], init: NonNullable<Parameters<typeof fetchSync>[1]>): any & { at: number, at2: string } {
  const origNodeOptions = process.env.NODE_OPTIONS;
  if (origNodeOptions !== undefined) {
    process.env.NODE_OPTIONS = strNodeOptionsRemoveInspect(origNodeOptions);
  }
  const resp = fetchSync(url, init);
  const respTxt = resp.text();
  if (origNodeOptions !== undefined) {
    process.env.NODE_OPTIONS = origNodeOptions;
  }
  if (!resp.ok) {
    const statusText = resp.statusText === "401" ? "Unauthorized" : resp.statusText; // why not "Unauthorized"? bug?
    logger.error(`${init.method} ${url}: ${resp.status} ${statusText}`);
    logger.warn(`respTxt: ${respTxt}`);
    throw new AppError(`GET ${url}: ${resp.status} ${statusText}`);
  }
  const json = JSON.parse(respTxt);
  _cflmdFetchJSONCheckJSON(json);
  return json;
}
// @ts-expect-error
globalThis.cflmdFetchJSONSync_ = cflmdFetchJSONSync; // cannot evaluate cflmdFetchJSONSync in debugger break'ed in functions which do not use this function; then use cflmdFetchJSONSync_()

function _cflmdFetchJSONCheckJSON(json: any): void {
  if (!("results" in json)) {
    assert.ok(!("size" in json));
    assert.ok(!("start" in json));
    return;
  }
  assert.ok(json.results.length === json.size);
  assert.ok(json.start === 0);
  // assert.ok(json.limit === 50);
  if (json.size > json.limit) {
    debugger;
    throw new AppError(`TODO: implement pagination (size: ${json.size}, limit: ${json.limit})\n\n${json}\n`);
  }
}

/*
<!--
[title](url)
-->
*/
type CflmdFile = {
  path: string, // file path
  title: string,
  url: {
    // https://wiki.sei.cmu.edu/confluence/pages/viewpage.action?pageId=87152044
    type: "id",
    urlConfluenceTop: string, // https://wiki.sei.cmu.edu/confluence
    id: number,
  } | {
    // https://wiki.sei.cmu.edu/confluence/display/c/SEI+CERT+C+Coding+Standard
    type: "kt",
    urlConfluenceTop: string, // https://wiki.sei.cmu.edu/confluence
    spaceKey: string, // c
    webuiTitle: string, // SEI+CERT+C+Coding+Standard
  },
};

interface CflmdPage {
  at: number; // 1136214845
  at2: string; // "2006-01-02 15:04:05"
  // from REST
  id: string;
  type: "page",
  status: "current",
  title: string;
  body: { storage: { value: string } };
  space: {
    id: number;
    key: string;
    name: string;
  };
  version: { number: number; };
  _links: { webui: string; };
};

async function cflmdPagePut(opts: Parameters<typeof cflmd>[1], file: CflmdFile, body_: string, pagePromise: Promise<CflmdPage>): Promise<CflmdPage> {
  const at = Date.now();
  const at2 = new Date(at).toLocaleString("sv-SE");
  const headers = { "Authorization": `Basic ${Buffer.from(`${opts.user}:${opts.token}`).toString("base64")}`, "Accept": "application/json", "Content-Type": "application/json" };
  const page = await pagePromise;
  const body = JSON.stringify({
    type: page.type,
    title: file.title,
    body: { storage: { value: body_, representation: "storage" } },
    version: { number: page.version.number + 1 },
  });
  const fetchJSONOpts = {
    logFetch: (...params: any) => logger.info(...params, `(current title: ${page.title})`),
    cache: { type: "w" as const, path: `${DIR_CACHE}/cflmd/api/content/${page.id}.json.PUT` },
  }
  const json = await cflmdFetchJSON(`${file.url.urlConfluenceTop}/rest/api/content/${page.id}?expand=body.storage,space,version`, { method: "PUT", headers, body }, fetchJSONOpts);
  // update GET cache file
  {
    const fetchJSONOpts = {
      logFetch: logger.debug.bind(logger),
      cache: { type: "w" as const, path: `${DIR_CACHE}/cflmd/api/content/${json.id}.json` },
    };
    const json2 = await cflmdFetchJSON(`${file.url.urlConfluenceTop}/rest/api/content/${json.id}?expand=body.storage,space,version`, { method: "GET", headers }, fetchJSONOpts);
    bp();
  }
  return json;
}

async function cflmdPageGet(opts: Parameters<typeof cflmd>[1], urlParsed: CflmdFile["url"]): Promise<CflmdPage> {
  const headers = { "Authorization": `Basic ${Buffer.from(`${opts.user}:${opts.token}`).toString("base64")}`, "Accept": "application/json" };

  if (urlParsed.type === "id") {
    const fetchJSONOpts = {
      logFetch: logger.debug.bind(logger),
      cache: { type: "rw" as const, path: `${DIR_CACHE}/cflmd/api/content/${urlParsed.id}.json`, validSecs: opts.cacheSecsPage, validSecsOpt: "--cache-secs-page/CFLMD_CACHE_SECS_PAGE" },
    };
    const json = await cflmdFetchJSON(`${urlParsed.urlConfluenceTop}/rest/api/content/${urlParsed.id}?expand=body.storage,space,version`, { method: "GET", headers }, fetchJSONOpts);
    return json;
  } else {
    const fetchJSONOpts = {
      logFetch: logger.debug.bind(logger),
      // NOTE: spaceKey and webuiTitle may contain special characters so may cause errors
      cache: { type: "rw" as const, path: `${DIR_CACHE}/cflmd/api/content/${urlParsed.spaceKey}/${urlParsed.webuiTitle}.json`, validSecs: opts.cacheSecsPage, validSecsOpt: "--cache-secs-page/CFLMD_CACHE_SECS_PAGE" },
    };
    const json = await cflmdFetchJSON(`${urlParsed.urlConfluenceTop}/rest/api/content?spaceKey=${urlParsed.spaceKey}&title=${urlParsed.webuiTitle}&expand=body.storage,space,version`, { method: "GET", headers }, fetchJSONOpts);
    if (json.results.length === 0) {
      // spaceKey exists, but title not found
      //   https://wiki.sei.cmu.edu/confluence/rest/api/content?spaceKey=c&title=nonexistent_title    {"results":[],"start":0,"limit":25,"size":0,"_links":{"self":"https://wiki.sei.cmu.edu/confluence/rest/api/content?spaceKey=c&title=nonexistent_title","base":"https://wiki.sei.cmu.edu/confluence","context":"/confluence"}}
      //   https://wiki.sei.cmu.edu/confluence/rest/api/content?spaceKey=x&title=nonexistent_title    {"statusCode":404,"data":{"authorized":false,"valid":true,"allowedInReadOnlyMode":true,"errors":[],"successful":false},"message":"No space with key : x","reason":"Not Found"}
      throw new AppError(`page not found: ${urlParsed.urlConfluenceTop}/rest/api/content?spaceKey=${urlParsed.spaceKey}&title=${urlParsed.webuiTitle}`);
    }
    if (json.results.length > 1) {
      throw new AppError(`BUG: multiple pages found: ${urlParsed.urlConfluenceTop}/rest/api/content?spaceKey=${urlParsed.spaceKey}&title=${urlParsed.webuiTitle}`);
    }
    json.results[0].at = json.at;
    json.results[0].at2 = json.at2;
    return json.results[0];
  }
  unreachable();
}

function cflmdParseURL(url: string): CflmdFile["url"] {
  let matchN: RegExpMatchArray | null;
  if (!URL.canParse(url)) {
    throw new AppError(`invalid URL: ${url}`);
  }
  matchN = url.match(/^(?<urlConfluenceTop>.+?)\/pages\/viewpage.action\?pageId=(?<id>[0-9]+)$/);
  if (matchN !== null) {
    return { type: "id", urlConfluenceTop: matchN.groups!.urlConfluenceTop, id: parseInt(matchN.groups!.id) };
  }
  matchN = url.match(/^(?<urlConfluenceTop>.+?)\/display\/(?<spaceKey>[^/]+)\/(?<title>[^/]+)$/);
  if (matchN !== null) {
    return { type: "kt", urlConfluenceTop: matchN.groups!.urlConfluenceTop, spaceKey: matchN.groups!.spaceKey, webuiTitle: matchN.groups!.title };
  }
  throw new AppError(`invalid URL: ${url}`);
}
// NODE_OPTIONS="--enable-source-maps --import @power-assert/node" CTS_TEST=all c.js
if (process.env.CTS_TEST === "all" || process.env.CTS_TEST === "cflmd") {
  assert.ok(util.isDeepStrictEqual(cflmdParseURL(`https://wiki.sei.cmu.edu/confluence/pages/viewpage.action?pageId=87152044`), { type: "id", urlConfluenceTop: "https://wiki.sei.cmu.edu/confluence", id: 87152044 }));
  assert.ok(util.isDeepStrictEqual(cflmdParseURL(`https://wiki.sei.cmu.edu/confluence/display/c/SEI+CERT+C+Coding+Standard`), { type: "kt", urlConfluenceTop: "https://wiki.sei.cmu.edu/confluence", spaceKey: "c", title: "SEI+CERT+C+Coding+Standard" }));
  assert.throws(() => cflmdParseURL(`https://wiki.sei.cmu.edu/confluence/display/c/SEI+CERT+C+Coding+Standard/INVALID`), AppError);
}

interface CflmdProcessArgs {
  file: CflmdFile;
  opts: Parameters<typeof cflmd>[1];
  pagePromise: ReturnType<typeof cflmdPageGet>;
  txts: { name: string; txt: string }[];
}

async function cflmdProcess1MarkdownPreProcess(args: CflmdProcessArgs): Promise<string> {
  let txt = args.txts.at(-1)!.txt;
  let name;

  name = "1.prep.0_cat.md"         ; txt = txtMarkdownCat(txt)                                       ; cflmdWrite(args.txts, name, txt, true); // @cat
  name = "1.prep.1_private.md"     ; txt = txtPrivate(txt, { preservePlp: false })                   ; cflmdWrite(args.txts, name, txt, true); //
  name = "1.prep.3_code_b64.md"    ; txt = txtMarkdownCodeB64(txt)                                   ; cflmdWrite(args.txts, name, txt, true); //
  name = "1.prep.4_h2_hidden.md"   ; txt = cflmdProcess1MarkdownPreProcessCflmdHidden(txt, args)     ; cflmdWrite(args.txts, name, txt, true); // @cflmd:hidden @private
  name = "1.prep.5_h2.md"          ; txt = txtMarkdownH2SectionReduce(txt)                           ; cflmdWrite(args.txts, name, txt, true); // ## foo - bar -> ## foo ### bar
  name = "1.prep.images.md"        ; txt = await cflmdProcess1MarkdownPreProcessImages(txt, args)    ; cflmdWrite(args.txts, name, txt, true); // ![alt](image.png)
  name = "1.prep.info.md"          ; txt = cflmdProcess1MarkdownPreProcessInfo(txt, args)            ; cflmdWrite(args.txts, name, txt, true); // <cflmd:info>
  name = "1.prep.misc.md"          ; txt = cflmdProcess1MarkdownPreProcessMisc(txt, args)            ; cflmdWrite(args.txts, name, txt, true); //
  name = "1.prep.toc.md"           ; txt = cflmdProcess1MarkdownPreProcessTOC(txt, args)             ; cflmdWrite(args.txts, name, txt, true); // @cflmd:toc
  name = "1.prep.z_code_b64d.md"   ; txt = txtMarkdownCodeB64d(txt)                                  ; cflmdWrite(args.txts, name, txt, true); //
  name = "1.prep.zz_code_macro.md" ; txt = cflmdProcess1MarkdownPreProcessZZCodeMacro(txt, args)     ; cflmdWrite(args.txts, name, txt, true); //
  cflmdWrite(args.txts, "1.prep.preprocess.md", txt, true);

  return txt;
}

// remove: ## @cflmd:hidden
function cflmdProcess1MarkdownPreProcessCflmdHidden(txt: string, args: CflmdProcessArgs): string {
  txt = txt + "\0";
  // eslint-disable-next-line no-control-regex
  for (const match of txt.matchAll(/^## .*@cflmd:hidden\b.*$[\s\S]+?(?=(^## |\x00))/gm)) {
    txt = txt.replace(match[0], "");
  }
  for (const match of txt.matchAll(/^## .*@private\b.*$[\s\S]+?(?=(^## |\x00))/gm)) {
    txt = txt.replace(match[0], "");
  }
  // compatibility: @cfmd:hidden
  // eslint-disable-next-line no-control-regex
  for (const match of txt.matchAll(/^## .*@cfmd:hidden.*$[\s\S]+?(?=(^## |\x00))/gm)) {
    txt = txt.replace(match[0], "");
  }
  txt = txt.slice(0, -1);
  return txt;
}

/*
*.png が絶対パスの場合は考慮していない
![](ubuntu.png)           | {"alt":"",               "path":"<path_on_conluence>"} | <ac:image                                   ac:height="${height_}"><ri:attachment ri:filename="${uploaded_path}" /></ac:image>
![@h:400](ubuntu.png)     | {"alt":"",   "h":"400",  "path":"<path_on_conluence>"} | <ac:image                                   ac:height="400"       ><ri:attachment ri:filename="${uploaded_path}" /></ac:image>
![@h:orig](ubuntu.png)    | {"alt":"",   "h":"orig", "path":"<path_on_conluence>"} | <ac:image                                                         ><ri:attachment ri:filename="${uploaded_path}" /></ac:image>
![alt](ubuntu.png)        | {"alt":"alt",            "path":"<path_on_conluence>"} | <ac:image ac:title="${alt}" ac:alt="${alt}" ac:height="${height_}"><ri:attachment ri:filename="${uploaded_path}" /></ac:image>
![alt@h:400](ubuntu.png)  | {"alt":"alt","h":"400",  "path":"<path_on_conluence>"} | <ac:image ac:title="${alt}" ac:alt="${alt}" ac:height="400"       ><ri:attachment ri:filename="${uploaded_path}" /></ac:image>
![alt@h:orig](ubuntu.png) | {"alt":"alt","h":"orig", "path":"<path_on_conluence>"} | <ac:image ac:title="${alt}" ac:alt="${alt}"                       ><ri:attachment ri:filename="${uploaded_path}" /></ac:image>

~/.cache/wataash/c.bash/cfl_content_attachment_get/<image_file>
~/.cache/wataash/cflmd/img/tmp.cfl_content_attachment_get.json
~/.cache/wataash/cflmd/img/sha1.<sha1>.json
*/
async function cflmdProcess1MarkdownPreProcessImages(txt: string, args: CflmdProcessArgs): Promise<string> {
  const images = [] as { imageTxt: string, alt: string, h?: string, path: string }[];
  for (const match of txt.matchAll(/(?<imageTxt>!\[(?<alt>.*?)(@h:(?<h>\d+|orig))?]\((?<path>.+?.png)\))/g)) {
    assert.ok(match.groups !== undefined);
    if (!path.isAbsolute(match.groups.path)) {
      match.groups.path = path.join(path.dirname(args.file.path), match.groups.path);
    }
    images.push(match.groups as any);
  }

  const page = await args.pagePromise;
  const headers = { "Authorization": `Basic ${Buffer.from(`${args.opts.user}:${args.opts.token}`).toString("base64")}`, "Accept": "application/json" };
  const fetchJSONOpts = {
    logFetch: logger.debug.bind(logger),
    cache: { type: "rw" as const, path: `${DIR_CACHE}/cflmd/api/content/${page.id}/child/attachment.json`, validSecs: args.opts.cacheSecsPage, validSecsOpt: "--cache-secs-page/CFLMD_CACHE_SECS_PAGE" },
  };
  const attachmentJSONPromise = cflmdFetchJSON(`${args.file.url.urlConfluenceTop}/rest/api/content/${page.id}/child/attachment`, { method: "GET", headers }, fetchJSONOpts);
  const attachmentJSON = await attachmentJSONPromise as {
    results: {
      id: string;
      type: "attachment";
      status: "current";
      title: string;
      metadata: { mediaType: string; labels: { results: any[] } };
      extensions: { mediaType: string; fileSize: number; comment: string };
      _links: { webui: string; download: string; thumbnail: string; self: string };
      _expandable: { container: string; operations: string; children: string; restrictions: string; history: string; descendants: string; space: string };
    }[];
  };

  for (const attachment of attachmentJSON.results) {
    // attachment._links.download; // /download/attachments/{pageId}/{fileName}?version=1&modificationDate={epochMilliseconds}&api=v2
    const fsPath = `${DIR_CACHE}/cflmd${attachment._links.download}`;
    const fetchJSONOpts = {
      logFetch: logger.debug.bind(logger),
      cache: { type: "rw" as const, path: fsPath, validSecs: args.opts.cacheSecsImg, validSecsOpt: "--cache-secs-img/CFLMD_CACHE_SECS_IMG" },
    }
    const buffer = await cflmdFetchBuffer(`${args.file.url.urlConfluenceTop}${attachment._links.download}`, { method: "GET", headers }, fetchJSONOpts);
    const sha1 = crypto.createHash("sha1").update(buffer).digest("hex");
    // @ts-expect-error
    attachment.at = attachmentJSON.at;
    // @ts-expect-error
    attachment.at2 = attachmentJSON.at2;
    fs.writeFileSync(`${fsPath}.json`, JSON.stringify(attachment, null, 2));
  }

  for (const image of images) {
    const sha1 = crypto.createHash("sha1").update(fs.readFileSync(image.path)).digest("hex");
    const cacheJSON = (() => {
      for (const f of fs.globSync(`${DIR_CACHE}/cflmd/download/attachments/${page.id}/*`)) {
        if (f.endsWith(".json")) continue;
        if (!fs.existsSync(f + ".json")) {
          logger.warn(`${f}.json not found`);
          continue;
        }
        const json = jsonParsePath(f + ".json");
        if (sha1 === crypto.createHash("sha1").update(fs.readFileSync(f)).digest("hex")) {
          return json;
        }
      }
      logger.warn("TODO: upload");
      debugger;
    })();
    if (image.h === undefined) {
      image.h = child_process.execFileSync("identify", ["-format", "%h", image.path], { encoding: "utf8" });
      if (parseInt(image.h) > 250) {
        image.h = "250";
      }
    }
    assert.ok(image.h !== undefined);
    // TODO: escape
    if      (image.alt === "" && image.h === "orig") txt = txt.replace(image.imageTxt, `<ac:image                                                                     ><ri:attachment ri:filename="${cacheJSON.title}" /></ac:image>`);
    else if (image.alt === "" && image.h !== "orig") txt = txt.replace(image.imageTxt, `<ac:image                                               ac:height="${image.h}"><ri:attachment ri:filename="${cacheJSON.title}" /></ac:image>`);
    else if (image.alt !== "" && image.h === "orig") txt = txt.replace(image.imageTxt, `<ac:image ac:title="${image.alt}" ac:alt="${image.alt}"                       ><ri:attachment ri:filename="${cacheJSON.title}" /></ac:image>`);
    else if (image.alt !== "" && image.h !== "orig") txt = txt.replace(image.imageTxt, `<ac:image ac:title="${image.alt}" ac:alt="${image.alt}" ac:height="${image.h}"><ri:attachment ri:filename="${cacheJSON.title}" /></ac:image>`);
    else unreachable();
  }

  return txt;
}

// <cflmd:info title="TITLE">  <cflmd:note title="TITLE">  <cflmd:tip title="TITLE">  <cflmd:warning title="TITLE">  title= はoptional
// BODY
// </cflmd:info>               </cflmd:note>               </cflmd:tip>               </cflmd:warning>
// ↓
// ```{=html}
// <ac:structured-macro ac:name="info" ac:schema-version="1" ac:macro-id="@cflmd:macro_id">  <!-- ac:name="info" ac:name="note" ac:name="tip" ac:name="warning" -->
// <ac:parameter ac:name="title">TITLE</ac:parameter>
// <ac:rich-text-body>
// ```
//
// BODY
//
// ```{=html}
// </ac:rich-text-body></ac:structured-macro>
// ```
function cflmdProcess1MarkdownPreProcessInfo(txt: string, args: CflmdProcessArgs): string {
  let reArr;
  while ((reArr = /<cflmd:(info|note|tip|warning)( title="(.+)")?>/.exec(txt)) !== null) {
    if (reArr[3] === undefined) txt = txt.replace(reArr[0], `\n\`\`\`{=html}\n<ac:structured-macro ac:name="${reArr[1]}" ac:schema-version="1" ac:macro-id="@cflmd:macro_id">\n<ac:rich-text-body>\n\`\`\`\n`);
    else                        txt = txt.replace(reArr[0], `\n\`\`\`{=html}\n<ac:structured-macro ac:name="${reArr[1]}" ac:schema-version="1" ac:macro-id="@cflmd:macro_id">\n<ac:parameter ac:name="title">${reArr[3] /*TODO:escape*/}</ac:parameter>\n<ac:rich-text-body>\n\`\`\`\n`);
  }
  while ((reArr = /<\/cflmd:(info|note|tip|warning)>/.exec(txt)) !== null) {
    txt = txt.replace(reArr[0], `\n\`\`\`{=html}\n</ac:rich-text-body></ac:structured-macro>\n\`\`\`\n`);
  }
  return txt;
}

function cflmdProcess1MarkdownPreProcessMisc(txt: string, args: CflmdProcessArgs): string {
  // checkbox
  // - [ ] aaa -> <ul class="task-list"> NL <li><label><input type="checkbox" />aaa</label></li> NL </ul>
  // - [x] aaa -> <ul class="task-list"> NL <li><label><input type="checkbox" checked="" />aaa</label></li> NL </ul>
  // prepend this,
  // - [ ] aaa -> - CFLMD_HACK_CHECKED_N aaa
  // - [x] aaa -> - CFLMD_HACK_CHECKED_Y aaa
  for (const match of txt.matchAll(/^( *- )\[([ x])\] /gm)) {
    txt = txt.replace(match[0], `${match[1]}${match[2] === " " ? "CFLMD_HACK_CHECKED_N" : "CFLMD_HACK_CHECKED_Y"} `);
  }

  // link
  // [](file:///etc)                          -> /etc
  // [](file://etc)                           -> etc
  let reArr;
  while ((reArr = new RegExp(String.raw`\[]\(file://(.+?)\)`).exec(txt))) {
    if (false) { /* dummy */ }
    else                                                                     txt = txt.replace(reArr[0], reArr[1].replaceAll("$", "$$$$"));
  }
  return txt;
}

// @cflmd:toc -> <ac:structured-macro ac:name="toc" ac:schema-version="1" ac:macro-id="@cflmd:macro_id" />
function cflmdProcess1MarkdownPreProcessTOC(txt: string, args: CflmdProcessArgs): string {
  for (const match of txt.matchAll(/^@cflmd:toc$/gm)) {
    txt = txt.replace(match[0], `<ac:structured-macro ac:name="toc" ac:schema-version="1" ac:macro-id="@cflmd:macro_id" />`);
  }
  // compatibility: @cfmd:toc
  for (const match of txt.matchAll(/^@cfmd:toc$/gm)) {
    txt = txt.replace(match[0], `<ac:structured-macro ac:name="toc" ac:schema-version="1" ac:macro-id="@cflmd:macro_id" />`);
  }
  return txt;
}

// ```lang
// @cflmd:collapse
// @cflmd:title:TITLE
// BODY
// ```
// -> structured-macro xml
//
// ```${=html} は処理しない
//
// TODO: code blocks in Pandoc’s Markdown tables (|```lang|)
function cflmdProcess1MarkdownPreProcessZZCodeMacro(txt: string, args: CflmdProcessArgs): string {
  for (const match of txt.matchAll(/^```(?<l>.+)?\r?\n(?<c>^@cflmd:collapse\r?\n)?(^@cflmd:title:(?<t>.+)\r?\n)?(?<b>[\s\S]+?)\r?\n```$/gm)) {
    assert.ok(match.groups !== undefined);
    const codeBlockLang = match.groups.l; // string?
    const collapse = match.groups.c; // string?
    const title = match.groups.t; // string?
    const body = match.groups.b; // string

    if (codeBlockLang === "{=html}")
      continue;

    const cflLang = {
      actionscript3: "actionscript3",
      applescript: "applescript",
      bash: "bash",
      "c#": "c#",
      cpp: "cpp",
      css: "css",
      coldfusion: "coldfusion",
      delphi: "delphi",
      diff: "diff",
      erl: "erl",
      groovy: "groovy",
      xml: "xml",
      java: "java",
      jfx: "jfx",
      js: "js",
      php: "php",
      perl: "perl",
      text: "text",
      powershell: "powershell",
      py: "py",
      ruby: "ruby",
      sql: "sql",
      sass: "sass",
      scala: "scala",
      vb: "vb",
      yml: "yml",
      // my aliases
      "c++": "cpp",
      html: "xml",
      javascript: "js",
      pl: "perl",
      ps1: "powershell",
      python: "py",
      rb: "ruby",
      sh: "bash",
      ts: "js",
      txt: "text",
      typescript: "js",
      yaml: "yml"
    }[codeBlockLang] || undefined;

    // pandoc BUG? CDATA中に ">" が入っているとCDATAが空になる
    const body2 = body.replaceAll(">", "__CFLMD_HACK_CDATA_GT__");

    const xml = `<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="@cflmd:macro_id">${cflLang === undefined ? "" : `<ac:parameter ac:name="language">${cflLang}</ac:parameter>`}${title === undefined ? "" : `<ac:parameter ac:name="title">${title}</ac:parameter>`}${collapse === undefined ? "" : `<ac:parameter ac:name="collapse">true</ac:parameter>`}
      <ac:plain-text-body><![CDATA[${body2}
]]>
      </ac:plain-text-body>
    </ac:structured-macro>`;
    txt = txt.replace(match[0], xml.replaceAll("$", "$$$$"));
  }

  return txt;
}


async function cflmdProcess2Pandoc(args: CflmdProcessArgs): Promise<string> {
  let txt = args.txts.at(-1)!.txt;
  txt = child_process.execSync(`c.bash pandoc`, { input: txt, encoding: "utf8" });
  return txt;
}

async function cflmdProcess3HTMLPostProcess(args: CflmdProcessArgs): Promise<string> {
  let txt = args.txts.at(-1)!.txt;
  let match;

  // 0 HACK
  txt = txt.replaceAll("__CFLMD_HACK_CDATA_GT__", ">");
  txt = txt.replaceAll("CFLMD_HACK_CHECKED_N", "[ ]");
  txt = txt.replaceAll("CFLMD_HACK_CHECKED_Y", "[x]");
  cflmdWrite(args.txts, "0_hack.html", txt, true);

  // 1 line breaks
  // -pandoc-> <pre NL class="sourceCode sh">
  //    -PUT-> <pre class="sourceCode sh">
  for (const match of txt.matchAll(/<pre\s+class="sourceCode/g)) {
    txt = txt.replace(match[0], `<pre class="sourceCode`);
  }

  // code block
  // -pandoc-> <div class="sourceCode" id="cb1"> ... <span id="cb1-1"> ... <a href="#cb1-1" aria-hidden="true" tabindex="-1"></a>
  //    -PUT-> <div class="sourceCode">          ... <span>
  for (const match of txt.matchAll(/(<div\s+class="sourceCode"\s+id="cb\d+">)/g)) {
    txt = txt.replace(match[0], "<div class=\"sourceCode\">");
  }
  for (const match of txt.matchAll(/(<span\s+id="cb\d+-\d+">)/g)) {
    txt = txt.replace(match[0], "<span>");
  }
  for (const match of txt.matchAll(/(<a\s+href="#cb\d+-\d+"\s+aria-hidden="true"\s+tabindex="-1"><\/a>)/g)) {
    txt = txt.replace(match[0], "");
  }

  // link
  //
  // md: http://www.example.com/
  // -pandoc-> html:
  // <p><a href="http://www.example.com/"
  // class="uri">http://www.example.com/</a></p>
  // remove `class="uri"`:
  for (const match of txt.matchAll(/(<a\s+href=".+?")\s+class="uri">/g)) {
    txt = txt.replace(match[0], `${match[1]}>`);
  }
  // md: email@example.com -pandoc-> html:
  // <p><a href="mailto:email@example.com"
  // class="email">email@example.com</a></p>
  // -> email@example.com:
  txt = txt.replaceAll(/<a\s+href="mailto:.+?"\s+class="email">(.+?)<\/a>/g, "$1");
  // https://wiki.sei.cmu.edu/confluence/display/c/SEI+CERT+C+Coding+Standard
  // https://wiki.sei.cmu.edu/confluence/pages/viewpage.action?pageId=87152044
  // -> <ac:link><ri:page ri:content-title="SEI CERT C Coding Standard" /></ac:link>
  {
    const thisFileSpaceKey = (await args.pagePromise).space.key;
    let re = /<a\s+href="(?<href>__cfl_top__[^"]+)">(\k<href>)<\/a>/;
    re = reReplace(re, "__cfl_top__", args.file.url.urlConfluenceTop);
    while ((match = txt.match(re)) !== null) {
      assert.ok(match.groups !== undefined);
      const page = await cflmdPageGet(args.opts, cflmdParseURL(match.groups.href));
      if (page.space.key === thisFileSpaceKey) {
        // TODO: if link to self:   `<ac:link />`
        txt = txt.replace(match[0], `<a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK><ri:page                                  ri:content-title="${page.title}" /></a>`);
      } else {
        txt = txt.replace(match[0], `<a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK><ri:page ri:space-key="${page.space.key}" ri:content-title="${page.title}" /></a>`);
      }
    }
  }
  cflmdWrite(args.txts, "3.postp.link.html", txt, true);

  // table
  //
  //            <table style="width:74%;">
  //     -PUT-> <table style="width: 74.0%;">
  // change to: <table>
  while ((match = txt.match(/<table style="width:[0-9]{1,3}%;">/)) !== null) {
    txt = txt.replace(match[0], "<table>");
  }
  // md: grid_table https://pandoc.org/MANUAL.html#extension-grid_tables
  //  -pandoc-> <col style="width: 33%" />
  //     -PUT-> <col style="width: 33%" />
  // change to: <col />
  while ((match = txt.match(/<col style="width: [0-9]{1,3}%" \/>/)) !== null) {
    txt = txt.replace(match[0], "<col />");
  }
  // <table> --save on web UI--> <table class="wrapped">
  while ((match = txt.match(/<table>/)) !== null) {
    txt = txt.replace(match[0], `<table class="wrapped">`);
  }
  cflmdWrite(args.txts, "3.postp.table.html", txt, true);

  // z @cflmd:macro_id
  // if two macro IDs have the same value, the second one will be changed to a random value;
  // avoid using duplicate IDs
  let macroID = 0;
  while ((match = txt.match(/@cflmd:macro_id\b/g)) !== null) {
    txt = txt.replace(/@cflmd:macro_id\b/, `00000000-0000-0000-0000-${String(++macroID).padStart(12, "0")}`); // starts from 1: 00000000-0000-0000-0000-000000000001
  }
  // compatibility: @cfmd:macro_id
  while ((match = txt.match(/@cfmd:macro_id\b/g)) !== null) {
    txt = txt.replace(/@cfmd:macro_id\b/, `00000000-0000-0000-0000-${String(++macroID).padStart(12, "0")}`);
  }
  cflmdWrite(args.txts, "3.postp.z_macro_id.html", txt, true);

  return txt;
}

async function cflmdProcess4FormatHtml(args: CflmdProcessArgs): Promise<string> {
  let txt = args.txts.at(-1)!.txt;
  // without `cat |`: ENXIO -- I guess it's because fd 0 is unix socket (inspected by lsof)
  txt = child_process.execSync(`cat | c.js txt-confluence-html-format`, { input: txt, encoding: "utf8", env: { ...process.env, NODE_OPTIONS: "--enable-source-maps" } });
  return txt;
}

function cflmdWrite(txts: { name: string; txt: string }[], name: string, txt: string, doDiff: boolean) {
  txts.push({ name, txt });
  fs.writeFileSync(`${DIR_CACHE}/cflmd/last/${name}`, txt);
  if (!doDiff) return;
  // without maxBuffer or maxBuffer: 2**21 (2Mi): ENOBUFS
  // 2**26: 64Mi
  const diff = child_process.execSync(`diff -u ${DIR_CACHE}/cflmd/last/${txts.at(-2)!.name} ${DIR_CACHE}/cflmd/last/${name} || true`, { encoding: "utf8", maxBuffer: 2 ** 26 });
  fs.writeFileSync(`${DIR_CACHE}/cflmd/last/${name}.diff`, diff);
  if (diff === "") {
    fs.unlinkSync(`${DIR_CACHE}/cflmd/last/${name}.diff`);
  } else {
    logger.debug(`${DIR_CACHE}/cflmd/last/${name}.diff : ${diff.split(/\r?\n/).length - 1} lines`);
  }
}

// -----------------------------------------------------------------------------
// command - countdown

program.command("countdown").description("countdown description")
  .addArgument(new commander.Argument("<duration>", "e.g. 300, 3hour 4min 5sec (GNU date(1) style)").argParser(CLI.parseDuration))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["countdown"] = async function countdown(
  duration: number,
  opts: {
  },
) {
  let someOutputted = false;
  while (duration > 0) {
    if (duration === 1) {
      process.stdout.write("1");
    } else {
      process.stdout.write(`${duration} `);
    }
    someOutputted = true;
    duration--;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  someOutputted && process.stdout.write("\n");
  return cliCommandExit(0);
}

// -----------------------------------------------------------------------------
// command - exec-gdbproxy

program.command("exec-gdbproxy").description("exec-gdbproxy description")
  .addOption(new commander.Option("--gdb <path>", "gdb path").default("gdb"))
  .addArgument(new commander.Argument("[arg...]", "gdb arguments"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["exec-gdbproxy"] = async function (arg: string[], opts: { gdb: string }) {
  // TODO: dedent
    logger.info(`${opts.gdb} ${arg}`);
    const subprocess = child_process.spawn(opts.gdb, arg);
    const promiseSubprocessClosed: Promise<[number | null, NodeJS.Signals | null]> = new Promise((resolve, reject) => {
      subprocess.on("close", (code, signal) => {
        logger.info(`subprocess.on close`);
        resolve([code, signal]);
      });
    });
    subprocess.on("error", (err) => { throw err; });
    subprocess.stdin.on("error", (err) => { logger.error("stdin error", err); });
    subprocess.stdout.on("error", (err: Error) => { logger.error("stdout error", err); });
    subprocess.stderr.on("error", (err: Error) => { logger.error("stderr error", err); });
    subprocess.stdin.on("close", () => {
      logger.debug(`subprocess.stdin.on close`);
    });

    const decoderIn = new TextDecoder();
    const decoderOut = new TextDecoder();
    const decoderErr = new TextDecoder();

    let xGDBCmd: { dummyCmd: string, decoder: TextDecoder, buf: string } | null = null;

    process.stdin.on("end", () => {
      logger.debug(`[in end]`);
      subprocess.stdin.end();
    });
    process.stdin.on("data", (data) => {
      const txt = decoderIn.decode(data, { stream: true });
      // logger.debug(`[in] ${data} (${txt})`);
      logger.debug(`[in] ${data}`);
      if (zGDBCmdIn(txt)) return;
      subprocess.stdin.write(data);
    });
    subprocess.stdout.on("data", (chunk) => {
      const txt = decoderOut.decode(chunk, { stream: true });
      // logger.info(`[out] :${txt}`);
      logger.info(`[out] ${chunk}`);
      if (xGDBCmdOut(chunk)) return;
      process.stdout.write(chunk);
    });
    subprocess.stderr.on("data", (chunk) => {
      const txt = decoderOut.decode(chunk, { stream: true });
      // logger.error(`[err] ${txt}`);
      logger.error(`[err] ${chunk}`);
      process.stderr.write(chunk);
    });

    const [code, signal] = await promiseSubprocessClosed;

    // XXX: doesn't exit with "(gdb) q" or "--gdb=echo"
    // whyIsNodeRunning():
    // # PROCESSWRAP
    // dist/c.js:568                              - const subprocess = child_process.spawn(opts.gdb, arg);
    // node_modules/commander/lib/command.js:542  - return fn.apply(this, actionArgs);
    // node_modules/commander/lib/command.js:1502 - this._actionHandler(this.processedArgs),
    // node_modules/commander/lib/command.js:1386 - return fn();
    // node_modules/commander/lib/command.js:1501 - promiseChain = this._chainOrCall(promiseChain, () =>
    // node_modules/commander/lib/command.js:1265 - return subCommand._parseCommand(operands, unknown);
    setTimeout(() => {
      process.exit();
    }, 100);
    if (code === null) {
      logger.error(`TODO: code===null`, `signal:`, signal);
      return cliCommandExit(1);
    }
    return cliCommandExit(code);

    function zGDBCmdIn(txt: string) {
      //    0-interpreter-exec --thread 1 --frame 0 mi2 "226-cidr-var-create var56_xzbt * \"x:zbt\""
      // -> 0-interpreter-exec --thread 1 --frame 0 mi2 "226-cidr-var-create var56_xzbt * \"777\""
      const match = reExec(/^0-interpreter-exec --thread (\d+) --frame (\d+) mi2 "(\d+)-cidr-var-create (var\w+) \* \\"x:(?<cmd>.+?)\\""(\r?\n)$/, txt);
      if (typeof match === "string") return false;
      assert.ok(match.groups !== undefined);
      logger.info(match.groups.cmd);
      subprocess.stdin.write(`${match.groups.cmd}\n`);
      xGDBCmd = { dummyCmd: match[0].replace(`x:${match.groups.cmd}`, "777"), decoder: new TextDecoder(), buf: "" };
      return true;
    }

    function xGDBCmdOut(chunk: Parameters<typeof TextDecoder.prototype.decode>[0]) {
      if (xGDBCmd == null) return false;
      // success:
      // &"zbt\n"
      // ^done
      // (gdb)SPACE
      //
      // error:
      // &"zbt\n"
      // &"Traceback (most recent call last):\n"
      //  ...
      // &"Error occurred in Python: No stack.\n"
      // ^error,msg="Error occurred in Python: No stack."
      // (gdb)SPACE
      xGDBCmd.buf += xGDBCmd.decoder.decode(chunk, { stream: true });
      const match = reExec(/^&".+?\\n"(\r?\n)([\s\S]*?)\^.+(\r?\n)\(gdb\) (\r?\n)$/, xGDBCmd.buf);
      if (typeof match === "string") {
        logger.debug(`xGDBCmd: ${match}`);
        return;
      }
      logger.debug(`xGDBCmd: ok; write dummy: ${xGDBCmd.dummyCmd}`);
      subprocess.stdin.write(xGDBCmd.dummyCmd);
      xGDBCmd = null;
      return;
    }
};

// -----------------------------------------------------------------------------
// command - execGitDiffPatch

program.command("execGitDiffPatch").description("execGitDiffPatch description")
  .addArgument(new commander.Argument("<commit>"))
  .action((...args) => execGitDiffPatch(...args, true));

async function  execGitDiffPatch(
  commit: string,
  opts?: {},
  command?: commander.Command<unknown[]>,
  cli?: true,
) {
  const setx = logger.level >= Logger.Level.Debug ? "set -x; " : "";
  const revNearestBranchPoint = child_process.execSync(`${setx}git rev-list --boundary HEAD...${strEscapeShell(commit)} | grep '^-' | sed 's/^-//' | tail -n1`, { encoding: "utf8" }).replace(/(\r?\n)$/, "");
  logger.debug(`nearst branch point: ${revNearestBranchPoint}`);

  // git format-patch -k --stdout origin/master..HEAD -- ./ >/tmp/patch2; diff -u /tmp/patch /tmp/patch2  # same

  let patchA = child_process.execSync(`git format-patch -k --stdout ${strEscapeShell(revNearestBranchPoint)}..HEAD -- ./`, { encoding: "utf8" });
  let patchB = child_process.execSync(`git format-patch -k --stdout ${strEscapeShell(revNearestBranchPoint)}..${strEscapeShell(commit)} -- ./`, { encoding: "utf8" });
  [patchA, patchB] = [patchA, patchB].map((patch) => patch.replaceAll(/^From [0-9a-f]{40}/gm, "From __SHA1__"));
  const Diff = await import("diff");
  let diff = Diff.createPatch("__filename__", patchA, patchB);
  console.log(diff);
  // console.log([...tmp]);
  return cliCommandExit(0);
}

// -----------------------------------------------------------------------------
// command - exec-kill-orphan-script-fish

/*
USER     TT          PPID    SESS    PGID     PID CMD
root     ?              0       1       1       1 /sbin/init splash
wsh      ?              1 1319878 1319878 1319884   script -efq -c fish /tmp/wataash/script.tmp.G1ra6JJrep
wsh      pts/16   1319884 1319885 1319885 1319885     fish                                                   ← kill
wsh      ?              1    3728    3728    3728   /lib/systemd/systemd --user
wsh      ?           3728  111464  111464  111470     script -efq -c fish /tmp/wataash/script.tmp.uh273wUpda
wsh      pts/9     111470  111471  111471  111471       fish                                                 ← kill
wsh      ?              1 1229871 1229871 1229871   /bin/bash -i -l -c '/home/wsh/.vscode-server/cli/servers/Stable-__HEX__/server/node'  -p '"__HEX__" + JSON.stringify(process.env) + "__HEX__"'
wsh      ?        1229871 1229871 1229871 1229884     script -efq -c fish /tmp/wataash/script.tmp.Iipyak4EfJ
wsh      pts/5    1229884 1229885 1229885 1229885       fish
*/

program.command("exec-kill-orphan-script-fish").description("exec-kill-orphan-script-fish description")
// @ts-expect-error  
.action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["exec-kill-orphan-script-fish"] = async function (opts: {}) {
  // TODO: dedent
    const txt = child_process.execSync(`set -x; ps -e -o user,tty,ppid,sess,pgid,pid,cmd -H -ww`, { encoding: "utf8" });
    const lines = txt.replace(/(\r?\n)$/, "").split(/\r?\n/);
    const ssv = strParseSSV(txt);
    assert.ok(lines.length === ssv.length);

    type PID = string;

    interface Process {
      USER: string;
      TT: string;
      PPID: string;
      SESS: string;
      PGID: string;
      PID: PID;
      CMD: string;
    }

    interface ProcessMeta extends Process {
      _iLine: number;
      _line: string;
      children: ProcessMeta[];
      parent: ProcessMeta | null;
    }

    // @ts-expect-error
    const header: (StrParseSSVEntry & { valueTrimmed: keyof Process })[] = ssv[0];
    ssv.shift();

    // { USER: [0, 8], TT: [8, 14], ..., CMD: [49,9007199254740991] }
    // @ts-expect-error type of Object.fromEntries() is weak
    const nameCol: { [key in keyof Process]: [number, number] } = Object.fromEntries(header.map((line) => [line.valueTrimmed, [line.colStartTrimmed, line.colEndTrimmed]]));

    // { "0": { "PPID": "0", "PGID: "0", "PID": "0", "COMMAND": "[system]" } }
    const processes: { [key: PID]: ProcessMeta } = ssv.entries().reduce((acc, [iLine, line]) => {
      // @ts-expect-error
      const ps: ProcessMeta = { _iLine: iLine, _line: lines[iLine + 1], children: [], parent: "__uninitialized__" };
      for (const [iVal, val] of line.entries()) {
        ps[header[iVal].valueTrimmed] = val.valueTrimmed;
      }
      acc[ps.PID] = ps;
      return acc;
    }, {} as { [key: PID]: ProcessMeta });

    const psRoot = { _iLine: -1, _line: "psRoot", children: [], parent: null };
    for (const [pid, ps] of Object.entries(processes)) {
      ps.parent = processes[ps.PPID] ?? psRoot;
      ps.parent.children.push(ps);
    }
    assert.ok(processes[0] === undefined);
    assert.ok(processes[1] !== undefined);
    // @ts-expect-error
    assert.ok(processes[1].parent === psRoot);
    assert.ok(processes[2].parent === psRoot);
    // @ts-expect-error
    assert.ok(psRoot.children.length === 2);

    const processesScriptNoTTY = Object.values(processes).filter((ps) => ps.TT === "?" && /^script -efq -c fish .+$/.test(ps.CMD));
    const pidsShow = new Set<string>();
    // add script parents recursively
    for (let ps of [...processesScriptNoTTY]) {
      while (ps.parent !== null) {
        pidsShow.add(ps.PID);
        ps = ps.parent;
      }
    }
    // add script children recursively
    const psStack = [...processesScriptNoTTY];
    while (psStack.length !== 0) {
      const ps2 = psStack.pop()!;
      pidsShow.add(ps2.PID);
      psStack.push(...ps2.children);
    }

    logger.debug(lines[0]);
    for (const ps of [...pidsShow].map((pid) => processes[pid]).sort((a, b) => a._iLine - b._iLine)) {
      logger.debug(ps._line);
    }

    {
      const logLines = ["to kill:"];
      for (const ps of [...pidsShow].map((pid) => processes[pid]).sort((a, b) => a._iLine - b._iLine)) {
        logLines.push(`kill -TERM ${ps.PID.padEnd(10, " ")}# ${ps._line}`);
      }
      console.log(logLines.join("\n"));
    }

    return cliCommandExit(0);
};

program.command("execDiffPipe").description("execDiffPipe description")
  .addArgument(new commander.Argument("<cmd...>"))
  // .addOption(new commander.Option("--diff-cmd").default("diff -u"))
  .addOption(new commander.Option("--diff-cmd").default("delta --paging=never")) // XXX: .makeOptionMandatory(true) just for typing
  .addOption(new commander.Option("--keep-tmp").default(false))
  // @ts-expect-error inferred type `diffCmd: string | boolean` is wrong
  .action((cmd, opts) => execDiffPipe(cmd, { _cli: true, ...opts }));

async function  execDiffPipe(
  cmd: string[],
  opts: {
    _cli?: boolean,
    diffCmd: string,
    keepTmp: boolean,
  },
) {
  logger.info(`reading from stdin...`);
  const txt = await readStdin();
  logger.info(`length: ${txt.length}`);
  const txt2 = child_process.spawnSync(cmd[0], cmd.slice(1), { encoding: "utf8", env: strNodeOptionsRemoveInspectEnv(process.env), input: txt, maxBuffer: 2 ** 26, stdio: ["pipe", "pipe", "inherit"] }).stdout;
  const a = tmp.fileSync({ prefix: "c.ts.execDiffPipe" });
  const b = tmp.fileSync({ prefix: "c.ts.execDiffPipe" });
  if (!opts.keepTmp) {
    tmp.setGracefulCleanup();
  }
  logger.debug(`${a.name} ${txt.length}`)
  logger.debug(`${b.name} ${txt2.length}`)
  fs.writeFileSync(a.fd, txt);
  fs.writeFileSync(b.fd, txt2);
  const spawnSyncReturns = child_process.spawnSync(`${opts.diffCmd} ${a.name} ${b.name}`, { shell: true, stdio: "inherit" });
  if (spawnSyncReturns.error !== undefined) throw spawnSyncReturns.error;
  if (spawnSyncReturns.status === null) {
    assert.ok(spawnSyncReturns.signal !== null);
    logger.warn(`signal: ${spawnSyncReturns.signal}`);
    // return cliCommandExit(128 + spawnSyncReturns.signal); // want to get signal number...
    return cliCommandExit(128);
  }
  return cliCommandExit(spawnSyncReturns.status);
}

// -----------------------------------------------------------------------------
// command - exec-slow-paste

program.command("exec-slow-paste").description("exec-slow-paste description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["exec-slow-paste"] = async function (file: string | undefined, opts: {}) {
  // TODO: dedent
    let in_ = fs.readFileSync(file ?? "/dev/stdin");
    const origClipBoard = child_process.execSync("xsel -b -o");
    while (in_.length > 0) {
      child_process.execSync("xsel -b -i", { input: in_.slice(0, 2048) });
      // process.stdout.write(child_process.execSync("xsel -b -o"));
      child_process.execSync("xdotool key $(: --delay default 12ms) ctrl+shift+v");
      in_ = in_.slice(2048);
    }
    child_process.execSync("xsel -b -i", { input: origClipBoard });
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - exec-ssh-kill-sleeps

/*
ubuntu@tk2-214-16769 ~> ps -e -o user,lstart,tty,ppid,sess,pgid,pid,cmd -H -ww
USER                      STARTED TT          PPID    SESS    PGID     PID CMD
root     Tue Jul  2 17:26:20 2024 ?              0       0       0       2 [kthreadd]
lstart STARTED は機械的にcolumns判別不可能だ
USER    |                 STARTED TT          PPID    SESS    PGID     PID CMD
root    |Tue Jul  2 17:26:20 2024 ?              0       0       0       2 [kthreadd]
or
USER        |             STARTED TT          PPID    SESS    PGID     PID CMD
root     Tue|Jul  2 17:26:20 2024 ?              0       0       0       2 [kthreadd]

ubuntu@tk2-214-16769 ~> ps -e -o user,tty,ppid,sess,pgid,pid,cmd -H -ww
USER     TT          PPID    SESS    PGID     PID CMD
root     ?              0       0       0       2 [kthreadd]
root     ?              2       0       0       3   [rcu_gp]
root     ?              0       1       1       1 /sbin/init
root     ?              1     713     713     713   sshd: /usr/sbin/sshd -D [listener] 0 of 10-100 startups
root     ?            713  766855  766855  766855     sshd: ubuntu [priv]
ubuntu   ?         766855  766855  766855  766958       sshd: ubuntu@notty
ubuntu   ?         766958  766998  766998  766998         sleep 1209600
root     ?            713  766893  766893  766893     sshd: ubuntu [priv]
ubuntu   ?         766893  766893  766893  766996       sshd: ubuntu@notty
ubuntu   ?         766996  766997  766997  766997         sleep 1209600
root     ?            713  782856  782856  782856     sshd: ubuntu [priv]
ubuntu   ?         782856  782856  782856  782942       sshd: ubuntu@notty
ubuntu   ?         782942  782943  782943  782943         sleep 1209600
ubuntu   ?              1  766709  766709  766709   sleep 1209600

sleep の PID をkillすれば良さそう
*/

program.command("exec-ssh-kill-sleeps").description("exec-ssh-kill-sleeps description")
  .addArgument(new commander.Argument("<host>", "host").choices(["h", "h4", "s", "s4"])) // description "host" を渡すと -h に choices が表示される
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["exec-ssh-kill-sleeps"] = async function (host, opts: {}) {
  // TODO: dedent
    if (["h", "h4"].includes(host)) {
    }
    if (["s", "s4"].includes(host)) {
      const txt = child_process.execSync(`ssh ${host} -- ps -e -o user,tty,ppid,sess,pgid,pid,cmd -H -ww`, { encoding: "utf8" });
      const lines = txt.replace(/(\r?\n)$/, "").split(/\r?\n/);
      const ssv = strParseSSV(txt);
      assert.ok(lines.length === ssv.length);

      // { USER: [0, 8], TT: [8, 14], ..., CMD: [49,9007199254740991] }
      const nameCol = Object.fromEntries(ssv[0].map((line) => [line.valueTrimmed, [line.colStartTrimmed, line.colEndTrimmed]]));
      // { "0": { "PPID": "0", "PGID: "0", "PID": "0", "COMMAND": "[system]" } }
      const processes: { [key: string]: { [key: string]: string } & { _iLine: number, _line: string } } = {};

      for (const [iLine, line] of ssv.entries()) {
        if (iLine === 0) continue;
        // @ts-expect-error (TS2322 ts BUG?)
        const p: { [key: string]: string } & { _iLine: number, _line: string } = { _iLine: -1, _line: "__uninitialized__" };
        for (const [iVal, val] of line.entries()) {
          p[ssv[0][iVal].valueTrimmed] = val.valueTrimmed;
        }
        p._iLine = iLine;
        p._line = lines[iLine];
        processes[p.PID] = p;
      }

      const sleepPIDs = new Set(Object.entries(processes).filter(([pid, p]) => /^sleep \d+$/.test(p.CMD)).map(([pid, p]) => pid));
      const sleepTreePIDs = new Set();
      for (const sleepPID of sleepPIDs) {
        let p = processes[sleepPID];
        assert.ok(!sleepTreePIDs.has(p.PID));
        sleepTreePIDs.add(p.PID);
        while (1) {
          p = processes[p.PPID];
          if (p === undefined) break;
          if (sleepTreePIDs.has(p.PID)) break;
          sleepTreePIDs.add(p.PID);
        }
      }

      logger.debug(`kill PGIDs ${[...sleepPIDs].join(" ")}:`);
      logger.debug(lines[0]);
      // @ts-expect-error
      for (const p of [...sleepTreePIDs].map((pid) => processes[pid]).sort((a, b) => a._iLine - b._iLine)) {
        if (sleepPIDs.has(p.PID)) {
          assert.ok(p._line.at(nameCol.CMD[0]) === " "); // except for "/sbin/init"
          const line = p._line.slice(0, nameCol.CMD[0]) + "*" + p._line.slice(nameCol.CMD[0] + 1);
          logger.debug(line);
        } else {
          logger.debug(p._line);
        }
      }
      if (sleepPIDs.size === 0) {
        logger.info("no sleep process found");
      } else {
        const cmd = `ssh ${host} -- kill -TERM ${[...sleepPIDs].join(" ")}`;
        logger.info(cmd);
        child_process.execSync(cmd, { encoding: "utf8", stdio: "inherit" });
      }
    }

    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - exec-tsserver-defs
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
      if (reArr[3].length < parseInt(reArr[2], 10)) {
        logger.debug(`short read: ${reArr[3].length} < ${reArr[2]}; buf:${this.buf}`);
        await new Promise((resolve) => {
          this.waiters.push({ resolve });
        });
        continue;
      }
      const content = this.buf.subarray(reArr[1].length, reArr[1].length + parseInt(reArr[2], 10));
      if (this.buf.length < reArr[1].length + parseInt(reArr[2], 10)) {
        unreachable();
      }
      this.buf = this.buf.subarray(reArr[1].length + parseInt(reArr[2], 10));
      if (this.buf.length > 0) {
        logger.debug(`leftover: ${this.buf.length} bytes`);
      }
      return content;
    }
    // NOTREACHED
  }
}

program.command("exec-tsserver-defs").description("exec-tsserver-defs description")
// @ts-expect-error  
.action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["exec-tsserver-defs"] = async function (opts: {}) {
  // TODO: dedent
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
      subprocess.stdin.write(`${s}\r\n`);
    };

    sh(`mkdir -p /tmp/vscode/`);
    const subprocess = child_process.spawn("tsserver");
    const r = new ExecTSServerDefsHTTPReader(subprocess.stdout);
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
};

// -----------------------------------------------------------------------------
// command - fs-diff

program.command("fs-diff").description("fs-diff description")
  .addOption(new commander.Option("--sudo").default(false))
  .addArgument(new commander.Argument("<dirA>"))
  .addArgument(new commander.Argument("<dirB>"))
  .usage("[options] [rsyncOpts] <dirA> <dirB>")
  .allowUnknownOption(true)
  // @ts-expect-error
  .allowExcessArguments(true).action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["fs-diff"] = async function (...args) {
  // TODO: dedent
    const command: commander.Command = args.pop();
    // @ts-expect-error
    const opts: { sudo: boolean } = command.opts();
    const dirB: string = command.args.pop()!;
    const dirA: string = command.args.pop()!;
    const rsyncOpts: string[] = command.args;
    const rsyncOpts_ :string = rsyncOpts.map((s) => strEscapeShell(s)).join(" ");

    // when -n/--dry-run is specified:
    // - -n and --dry-run are equivalent, but to be extra cautious to prevent accidental data loss
    // - -S does nothing, but I want it when the command copy-pasted and `-n --dry-run` removed

    logger.info(`diff ${dirA} ${dirB}`);
    cp.execSync(`PS4='+ \\e[32m''cmd: \\e[0m'; set -x; ${opts.sudo ? "sudo " : ""}rsync -rlp$(: t)goD -ciuSv -n --dry-run --delete ${rsyncOpts_} ${strEscapeShell(dirA)} ${strEscapeShell(dirB)}`, { shell: "bash", stdio: "inherit" });
    logger.info(`diff ${dirB} ${dirA}`);
    cp.execSync(`PS4='+ \\e[32m''cmd: \\e[0m'; set -x; ${opts.sudo ? "sudo " : ""}rsync -rlp$(: t)goD -ciuSv -n --dry-run --delete ${rsyncOpts_} ${strEscapeShell(dirB)} ${strEscapeShell(dirA)}`, { shell: "bash", stdio: "inherit" });

    logger.info(`diff ${dirA} ${dirB}`);
    cp.execSync(`PS4='+ \\e[32m''cmd: \\e[0m'; set -x; ${opts.sudo ? "sudo " : ""}rsync -a -ciuSv -n --dry-run --delete ${rsyncOpts_} ${strEscapeShell(dirA)} ${strEscapeShell(dirB)}`, { shell: "bash", stdio: "inherit" });
    logger.info(`diff ${dirB} ${dirA}`);
    cp.execSync(`PS4='+ \\e[32m''cmd: \\e[0m'; set -x; ${opts.sudo ? "sudo " : ""}rsync -a -ciuSv -n --dry-run --delete ${rsyncOpts_} ${strEscapeShell(dirB)} ${strEscapeShell(dirA)}`, { shell: "bash", stdio: "inherit" });

    logger.info(`diff ${dirA} ${dirB}`);
    cp.execSync(`PS4='+ \\e[32m''cmd: \\e[0m'; set -x; ${opts.sudo ? "sudo " : ""}rsync -a -c$(: i)uSv -n --dry-run --delete ${rsyncOpts_} ${strEscapeShell(dirA)} ${strEscapeShell(dirB)}`, { shell: "bash", stdio: "inherit" });
    logger.info(`diff ${dirB} ${dirA}`);
    cp.execSync(`PS4='+ \\e[32m''cmd: \\e[0m'; set -x; ${opts.sudo ? "sudo " : ""}rsync -a -c$(: i)uSv -n --dry-run --delete ${rsyncOpts_} ${strEscapeShell(dirB)} ${strEscapeShell(dirA)}`, { shell: "bash", stdio: "inherit" });

    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - fs-large-files

program.command("fs-large-files").description("fs-large-files description")
  .addOption(new commander.Option("--entries <n>").default(1000).argParser(CLI.parseInt))
  .addArgument(new commander.Argument("<dir>"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["fs-large-files"] = async function (dir: string, opts: { entries: number }) {
  // TODO: dedent
    const glob = await import("glob");
    // TODO
    const b = glob.globStream("/home/wsh/doc/*");
    const a = glob.globSync("/home/wsh/doc/*");
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - fs-link-hard

program.command("fs-link-hard").description("fs-link-hard description")
  .addArgument(new commander.Argument("<dir>"))
  .addArgument(new commander.Argument("<dirSHA1>"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["fs-link-hard"] = async function (dir: string, dirSHA1: string, opts: {}) {
  // TODO: dedent
    fs.mkdirSync(dirSHA1, { recursive: true });
    const sha1s = new Set(fs.readdirSync(dirSHA1));

    function walk(dir: string) {
      const files = fs.readdirSync(dir, { withFileTypes: true });
      for (const file of files) {
        const path_ = `${dir}/${file.name}`;
        if (file.isFile()) {
          const sha1 = crypto.createHash("sha1").update(fs.readFileSync(path_)).digest("hex");
          if (sha1s.has(sha1)) {
            // assert.ok(fs.existsSync(`${dirSHA1}/${sha1}`));
            // XXX: non atomic
            fs.unlinkSync(path_);
            fs.linkSync(`${dirSHA1}/${sha1}`, path_);
          } else {
            // assert.ok(!fs.existsSync(`${dirSHA1}/${sha1}`));
            fs.linkSync(path_, `${dirSHA1}/${sha1}`);
            sha1s.add(sha1);
          }
        } else if (file.isDirectory()) {
          console.debug(`walk into ${path.join(dir, file.name)}`);
          walk(path.join(dir, file.name));
        } else if (file.isSymbolicLink()) {
          // console.debug(`ignore symbolic link: ${path_}`)
        } else {
          throw new Error(`unexpected file type: ${file}`);
        }
        "breakpoint".match(/breakpoint/);
      }
      "breakpoint".match(/breakpoint/);
    }

    walk(dir);
    console.info("done");
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - fs-link-sym

program.command("fs-link-sym").description("fs-link-sym description")
  .addArgument(new commander.Argument("<dir>"))
  .addArgument(new commander.Argument("<dirSHA1>"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["fs-link-sym"] = async function (dir: string, dirSHA1: string, opts: {}) {
  // TODO: dedent
    fs.mkdirSync(dirSHA1, { recursive: true });
    const sha1s = new Set(fs.readdirSync(dirSHA1));

    function walk(dir: string) {
      const files = fs.readdirSync(dir, { withFileTypes: true });
      for (const file of files) {
        const path_ = `${dir}/${file.name}`;
        if (file.isFile()) {
          const sha1 = crypto.createHash("sha1").update(fs.readFileSync(path_)).digest("hex");
          if (sha1s.has(sha1)) {
            // assert.ok(fs.existsSync(`${dirSHA1}/${sha1}`));
            // console.debug(`ln -s ${dirSHA1}/${sha1} ${path_}`);
            // XXX: non atomic
            fs.unlinkSync(path_);
            fs.symlinkSync(`${dirSHA1}/${sha1}`, path_);
          } else {
            // assert.ok(!fs.existsSync(`${dirSHA1}/${sha1}`));
            // console.debug(`[new sha1] ln -s ${dirSHA1}/${sha1} ${path_}`);
            // XXX: non atomic
            fs.renameSync(path_, `${dirSHA1}/${sha1}`);
            fs.symlinkSync(`${dirSHA1}/${sha1}`, path_);
            sha1s.add(sha1);
          }
        } else if (file.isDirectory()) {
          console.debug(`walk into ${path.join(dir, file.name)}`);
          walk(path.join(dir, file.name));
        } else if (file.isSymbolicLink()) {
          // console.debug(`ignore symbolic link: ${path_}`)
        } else {
          throw new Error(`unexpected file type: ${file}`);
        }
        "breakpoint".match(/breakpoint/);
      }
      "breakpoint".match(/breakpoint/);
    }

    walk(dir);
    console.info("done");
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - fs-link-sym-async

program.command("fs-link-sym-async").description("fs-link-sym-async description")
  .addArgument(new commander.Argument("<dir>"))
  .addArgument(new commander.Argument("<dirSHA1>"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["fs-link-sym-async"] = async function (dir: string, dirSHA1: string, opts: {}) {
  // TODO: dedent
    fs.mkdirSync(dirSHA1, { recursive: true });
    const sha1s = new Set(fs.readdirSync(dirSHA1));

    async function walk(dir: string) {
      const files = fs.readdirSync(dir, { withFileTypes: true });
      for (const file of files) {
        const path_ = `${dir}/${file.name}`;
        if (file.isFile()) {
          const sha1 = crypto.createHash("sha1").update(fs.readFileSync(path_)).digest("hex");
          if (sha1s.has(sha1)) {
            // if (!fs.existsSync(`${dirSHA1}/${sha1}`)) {
            //   console.warn(`not symlinked yet: ${dirSHA1}/${sha1}`);
            // }
            // XXX: non atomic
            fsPromise.unlink(path_).then(() => {
              // console.debug(`ln -s ${dirSHA1}/${sha1} ${path_}`);
              fsPromise.symlink(`${dirSHA1}/${sha1}`, path_);
            });
          } else {
            // assert.ok(!fs.existsSync(`${dirSHA1}/${sha1}`));
            // XXX: non atomic
            fsPromise.rename(path_, `${dirSHA1}/${sha1}`).then(() => {
              // console.debug(`[new sha1] ln -s ${dirSHA1}/${sha1} ${path_}`);
              fsPromise.symlink(`${dirSHA1}/${sha1}`, path_);
            });
            sha1s.add(sha1);
          }
        } else if (file.isDirectory()) {
          console.debug(`walk into ${path.join(dir, file.name)}`);
          await walk(path.join(dir, file.name));
        } else if (file.isSymbolicLink()) {
          // console.debug(`ignore symbolic link: ${path_}`)
        } else {
          throw new Error(`unexpected file type: ${file}`);
        }
        // await new Promise((resolve) => setTimeout(resolve, 0)); // slow
      }
      await new Promise((resolve) => setTimeout(resolve, 0));
    }

    await walk(dir);
    console.info("done");
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - fs-md-code-blocks

program.command("fs-md-code-blocks").description("fs-md-code-blocks description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["fs-md-code-blocks"] = async function (file: string | undefined, opts: {}) {
  // TODO: dedent
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    sh(`rm -frv /tmp/vscode_md/ && mkdir -p /tmp/vscode_md/`);
    let i = 0;
    let txtBody = "## test\n";
    for (const match of txt.matchAll(/^```(?<l>.+)?(\r?\n)(?<b>[\s\S]+?)(\r?\n)```$/gm)) {
      // const codeBlockLang = match.groups.l; // string?
      // const body = match.groups.b; // string
      // @ts-expect-error
      logger.info(`/tmp/vscode_md/${i}.md\t${match.groups.l}\t${(match.groups.b.match(/\n/g) || []).length + 1} lines`);
      txtBody += `\n${match[0]}\n`;
      fs.writeFileSync(`/tmp/md/${i}.md`, txtBody);
      i++;
    }
    return cliCommandExit(0);
};


// -----------------------------------------------------------------------------
// command - fs-sponge-if-changed (sponge)

program.command("fs-sponge-if-changed").alias("sponge").description("fs-sponge-if-changed description")
  .addArgument(new commander.Argument("<file>"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["fs-sponge-if-changed"] = async function (file: string, opts: {}) {
  // TODO: dedent
    const txt = fs.readFileSync("/dev/stdin", "utf8");
    if (fs.existsSync(file) && txt === fs.readFileSync(file, "utf8")) {
      logger.debug(`no change: ${file}`);
      return cliCommandExit(0);
    }
    logger.debug(`changed: ${file}`);
    fs.writeFileSync(file, txt);
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - http-clipboard-server

program.command("http-clipboard-server").description("http-clipboard-server description")
  .addOption(new commander.Option("--port <port>", "port number").default(3000).argParser(CLI.parseIntPort))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["http-clipboard-server"] = async function (opts: { port: number }) {
  // TODO: dedent
    const express = (await import("express")).default;
    const app = express();
    app.use(express.text()); // var type = opts.type || 'text/plain'
    app.get("/", async (req, res, next) => {
      logger.debug(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${iie(req.headers)}`);
      res.setHeader("Content-Type", "text/plain");
      // sh(`clipnotify -s clipboard`);
      res.send(sh(`xsel -b -o`));
    });
    // @ts-ignore
    app.post("/", (req, res, next) => {
      logger.debug(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${iie(req.headers)} | ${ie(req.body)}`);
      res.setHeader("Content-Type", "text/plain");
      if (typeof req.body !== "string") {
        return res.status(422).send(`invalid request body (${ie(req.body)}); not text/plain?`);
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
};

// -----------------------------------------------------------------------------
// command - http-sse-proxy

program.command("http-sse-proxy").description("http-sse-proxy description")
  .addOption(new commander.Option("--port <port>", "port number").default(3000).argParser(CLI.parseIntPort))
  .addArgument(new commander.Argument("<url>", "url to SSE-proxy"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["http-sse-proxy"] = async function (url: string, opts: { port: number }) {
  // TODO: dedent
    const express = (await import("express")).default;
    const app = express();
    app.get("/", async (req, res, next) => {
      logger.info(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${iie(req.headers)}`);
      res.setHeader("Content-Type", "text/event-stream");
      const subprocess = child_process.spawn(`curl -fSs --no-buffer -X ${req.method} ${strEscapeShell(url)}`, { shell: true });
      subprocess.stdout.on("data", (data) => {
        logger.debug(`spawn(): stdout: ${strSnip(data.toString(), 100)}`);
        // res.send(data);
        if (!res.write(data)) { // TODO: res.on("close", ...)
          subprocess.stdout.destroy(); // kill with SIGPIPE
          subprocess.stderr.destroy();
        }
      });
      subprocess.stderr.on("data", (data) => {
        logger.error(`spawn(): stderr: ${data}`);
        res.write(data);
      });
      subprocess.on("close", (code) => {
        logger.info(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${iie(req.headers)} | closed (spawn close code: ${code})`);
      });
    });
    app.listen(opts.port, () => {
      logger.info(`listening on ${opts.port}`);
    });
    await sleepForever();
    // return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - http-sse-tailf

program.command("http-sse-tailf").description("http-sse-tailf description")
  .addOption(new commander.Option("--port <port>", "port number").default(3000).argParser(CLI.parseIntPort))
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["http-sse-tailf"] = async function (file: string | undefined, opts: { port: number }) {
  // TODO: dedent
    const express = (await import("express")).default;
    const app = express();
    app.get("/", async (req, res, next) => {
      logger.info(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${iie(req.headers)}`);
      res.setHeader("Content-Type", "text/event-stream");
      const subprocess = child_process.spawn(`tail -F ${file ? strEscapeShell(file) : ""}`, { shell: true });
      subprocess.stdout.on("data", (data) => {
        logger.debug(`spawn(): stdout: ${strSnip(data.toString(), 100)}`);
        // res.send(data);
        if (!res.write(data)) {
          subprocess.stdout.destroy(); // kill with SIGPIPE
          subprocess.stderr.destroy();
        }
      });
      subprocess.stderr.on("data", (data) => {
        logger.error(`spawn(): stderr: ${data}`);
        res.write(data);
      });
      subprocess.on("close", (code) => {
        logger.info(`${req.ip} -> ${req.headers.host} ${req.method} ${req.url} ${iie(req.headers)} | closed (spawn close code: ${code})`);
      });
    });
    app.listen(opts.port, () => {
      logger.info(`listening on ${opts.port}`);
    });
    await sleepForever();
    // return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - net-etc-hosts

program.command("net-etc-hosts").description("net-etc-hosts description")
  .addArgument(new commander.Argument("<host...>", "e.g. example.com http://www.example.com/foo/ https://www.example.com/foo/"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["net-etc-hosts"] = async function (host: string[], opts: { connectUrl: string }) {
  // TODO: dedent
    for (const [i, h] of host.entries()) {
      if (h.includes("/")) {
        // http://www.example.com/foo/ -> www.example.com
        try {
          const url = new URL(h);
          logger.debug(`${h} -> ${url.hostname}`);
          host[i] = url.hostname;
        } catch (e) {
          if (!(e instanceof TypeError)) throw e;
          throw new AppError(`invalid <host>: ${e.message}: ${h}`);
        }
        continue;
      }
      // host
      try {
        new URL(`http://${h}`);
      } catch (e) {
        throw new AppError(`invalid <host>: ${h}`);
      }
    }
    // const lookupAddresses: dns.LookupAddress[] = await Promise.all(host.map((h) => util.promisify(dns.lookup)(h)));
    const promises = [];
    for (const h of host) {
      // const lookupAddress: dns.LookupAddress = await util.promisify(dns.lookup)(h);
      const promise = util.promisify(dns.lookup)(h, {all: true}).then((lookupAddresses) => {
        for (const lookupAddress of lookupAddresses) {
          switch (lookupAddress.family) {
            // 0000:0000:0000:0000:0000:0000:0000:0000 39 chars
            case 4: process.stdout.write(`${lookupAddress.address.padEnd(39)} ${h.padEnd(49)} ## A; added by ${progname} net-etc-hosts\n`); break;
            case 6: process.stdout.write(`${lookupAddress.address.padEnd(39)} ${h.padEnd(49)} ## AAAA; added by ${progname} net-etc-hosts\n`); break;
            default:
              throw new AppError(`BUG: unexpected family: ${lookupAddress.family} (host: ${lookupAddress.address}, lookupAddress: ${util.inspect(lookupAddress)})`);
          }
        }
      });
      promises.push(promise);
    }
    await Promise.all(promises);
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - pty-cmd

program.command("pty-cmd").description("pty-cmd description")
  .addArgument(new commander.Argument("<cmd...>", "run <cmd> in a new pty"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["pty-cmd"] = async function (cmd: string[], opts: {}) {
  // TODO: dedent
    const pty = await import("node-pty");

    const exitCode = new Queue<number>();

    // Ubuntu 20.04: $TERM default is xterm?
    // systemd-run --user -- (which c.js) pty-cmd -- env  # TERM=xterm
    const ptyProcess = pty.spawn("sh", ["-c", strCommandsToShC(cmd)], {
      cols: process.stdout.columns,
      rows: process.stdout.rows,
    });

    ptyProcess.onData((data) => {
      // c.js pty-cmd -- /bin/echo -e 'a\x01z'  # [<- cmd](5) [ 'a', '\x01', 'z', '\r', '\n' ]   \x01: ^A
      // c.js pty-cmd -- /bin/echo -e 'a\xffz'  # [<- cmd](5) [ 'a', '�', 'z', '\r', '\n' ]      \xff: invalid utf8 -> �
      logger.debug(`[<- cmd](${data.length}) %O`, ...data);
      process.stdout.write(data);
    });

    ptyProcess.onExit((e) => {
      logger.info(`[cmd exit]`, e);
      // should dispose .onData()/.onExit() ?
      exitCode.push(e.exitCode);
    });

    if (process.stdin.isTTY) {
      process.stdin.setRawMode(true);
    } else {
      logger.info("stdin is not a tty; skip stdin.setRawMode(true)");
    }
    let tilde = false;
    process.stdin.on("data", (data: Buffer) => {
      const byteArray = [...data];
      logger.debug(`[-> cmd](${data.length}) ${ie([...data.toString()])}`);

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
};

function ptyCmdHandleEscape(ptyProcess: pty_.IPty, data: Buffer, previousTilde: boolean): "in_tilde" | "out_tilde" | "exit" {
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
// command - txt-color-complementary

program.command("txt-color-complementary").description("txt-color-complementary description")
  .addArgument(new commander.Argument("[color]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-color-complementary"] = async function (color: string | undefined, opts: {}) {
  // TODO: dedent
    const txt = color ?? fs.readFileSync("/dev/stdin", "utf8");
    const match = /^(?<hash>#?)(?<r>[0-9a-f]{2})(?<g>[0-9a-f]{2})(?<b>[0-9a-f]{2})(\r?\n)?$/i.exec(txt);
    if (match === null) {
      throw new AppError(`invalid color code: ${txt}`);
    }
    const r = parseInt(match.groups!.r, 16);
    const g = parseInt(match.groups!.g, 16);
    const b = parseInt(match.groups!.b, 16);
    // https://www.wave440.com/php/iro.php
    const maxMin = Math.max(r, g, b) + Math.min(r, g, b);
    process.stdout.write(`${match.groups!.hash}${(maxMin - r).toString(16).padStart(2, "0")}${(maxMin - g).toString(16).padStart(2, "0")}${(maxMin - b).toString(16).padStart(2, "0")}\n`);
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - txt-color-invert

program.command("txt-color-invert").description("txt-color-invert description")
  .addArgument(new commander.Argument("[color]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-color-invert"] = async function (color: string | undefined, opts: {}) {
  // TODO: dedent
    const txt = color ?? fs.readFileSync("/dev/stdin", "utf8");
    const match = /^(?<hash>#?)(?<r>[0-9a-f]{2})(?<g>[0-9a-f]{2})(?<b>[0-9a-f]{2})(\r?\n)?$/i.exec(txt);
    if (match === null) {
      throw new AppError(`invalid color code: ${txt}`);
    }
    const r = parseInt(match.groups!.r, 16);
    const g = parseInt(match.groups!.g, 16);
    const b = parseInt(match.groups!.b, 16);
    process.stdout.write(`${match.groups!.hash}${(255 - r).toString(16).padStart(2, "0")}${(255 - g).toString(16).padStart(2, "0")}${(255 - b).toString(16).padStart(2, "0")}\n`);
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - txt-confluence-html-format

program.command("txt-confluence-html-format").description("txt-confluence-html-format description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-confluence-html-format"] = async function (file: string | undefined, opts: {}) {
  // TODO: dedent
    let txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");

    txt = txtHTMLCDataB64(txt);

    // echo 'https://example.com/123456789012345678901234567890123456789'   | c.bash pandoc  # <p><a    href="https://example.com/123456789012345678901234567890123456789"  NL class="uri">https://example.com/123456789012345678901234567890123456789</a></p>
    // echo 'https://example.com/1234567890123456789012345678901234567890'  | c.bash pandoc  # <p><a NL href="https://example.com/1234567890123456789012345678901234567890" NL class="uri">https://example.com/1234567890123456789012345678901234567890</a></p> --this process--> <p><a href...
    // for (const match of txt.matchAll(/<a(\r?\n)(https?:\/\/[^\s]+)/g)) {

    // " -> &quot;
    // preserving: <tag attr="value">
    while ((reArr = />([^<]*)"/.exec(txt)) !== null) {
      txt = txt.replace(reArr[0], `>${reArr[1]}&quot;`);
    }

    // <ac:structured-macro ac:macro-id="00000000-0000-0000-0000-000000000001" ac:name="expand" ac:schema-version="1"><ac:parameter ac:name="title">TITLE</ac:parameter><ac:rich-text-body>
    // ↓
    // <ac:structured-macro ac:name="expand" ac:schema-version="1" ac:macro-id="00000000-0000-0000-0000-000000000001"><ac:parameter ac:name="title">TITLE</ac:parameter><ac:rich-text-body>
    while ((reArr = /<ac:structured-macro ac:macro-id="(.+?)" ac:name="(expand|html)" ac:schema-version="1">/.exec(txt)) !== null) {
      txt = txt.replace(reArr[0], `<ac:structured-macro ac:name="${reArr[2]}" ac:schema-version="1" ac:macro-id="${reArr[1]}">`);
    }

    // <ac:plain-text-body> \n <![CDATA[ → <ac:plain-text-body><![CDATA[
    while ((reArr = /<ac:plain-text-body>\s+<!\[CDATA\[/.exec(txt)) !== null) {
      txt = txt.replace(reArr[0], `<ac:plain-text-body><![CDATA[`);
    }

    // <ac:...> \n <ac:...> → <ac:...><ac:...>
    // example:
    // <ac:structured-macro ac:name="html" ac:schema-version="1" ac:macro-id="00000000-0000-0000-0000-000000000001">
    //   <ac:plain-text-body>
    // <![CDATA[
    // ↓
    // <ac:structured-macro ac:name="html" ac:schema-version="1" ac:macro-id="00000000-0000-0000-0000-000000000001"><ac:plain-text-body><![CDATA[
    while ((reArr = /(<ac:[^>]+>)\s+<ac:/.exec(txt)) !== null) {
      txt = txt.replace(reArr[0], `${reArr[1]}<ac:`);
    }

    // </ac:...> \n <ac:...> → </ac:...><ac:...>
    // example:
    // <p><ac:structured-macro ac:name="code" ...><ac:parameter ac:name="language">bash</ac:parameter> <ac:plain-text-body><![CDATA[
    // ↓
    // <p><ac:structured-macro ac:name="code" ...><ac:parameter ac:name="language">bash</ac:parameter><ac:plain-text-body><![CDATA[
    while ((reArr = /(<\/ac:[^>]+>)\s+<ac:/.exec(txt)) !== null) {
      txt = txt.replace(reArr[0], `${reArr[1]}<ac:`);
    }

    // </ac:...> \n </ac:...> → </ac:...></ac:...>
    // example:
    // </ac:plain-text-body> </ac:structured-macro></p>
    // ↓
    // </ac:plain-text-body></ac:structured-macro></p>
    while ((reArr = /(<\/ac:[^>]+>)\s+<\/ac:/.exec(txt)) !== null) {
      txt = txt.replace(reArr[0], `${reArr[1]}</ac:`);
    }

    // exception:
    //                     </ac:structured-macro> **\n** <ac:structured-macro ...
    // </ac:rich-text-body></ac:structured-macro> **\n** </ac:rich-text-body></ac:structured-macro>
    while ((reArr = /<\/ac:structured-macro>(<\/?ac:)/.exec(txt)) !== null) {
      txt = txt.replace(reArr[0], `</ac:structured-macro>\n${reArr[1]}`);
    }

    txt = txtHTMLCDataB64d(txt);

    // ]]> </ac:plain-text-body></ac:structured-macro></p>
    // ↓
    // ]]></ac:plain-text-body></ac:structured-macro></p>
    while ((reArr = /]]>\s+<\/ac:plain-text-body>/.exec(txt)) !== null) {
      txt = txt.replace(reArr[0], `]]></ac:plain-text-body>`);
    }

    process.stdout.write(txt);
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - txt-emoji

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
  // @ts-expect-error
  text.match(emojiRegex).map((emoji) => emoji.length); // [1, 1, 2, 2, 2, 2, 4, 4] bytes?
  // @ts-expect-error
  text.match(emojiRegex).map((emoji) => [...emoji]); // [["⌚"], ["⌚"], ["↔", "️"], ["↔", "️"], ["👩"], ["👩"], ["👩", "🏿"], ["👩", "🏿"]] code points
  // @ts-expect-error
  text.match(emojiRegex).map((emoji) => [...emoji].length); // [1, 1, 2, 2, 1, 1, 2, 2] code points
}

program.command("txt-emoji").description("txt-emoji description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-emoji"] = async function (file: string | undefined, opts: {}) {
  // TODO: dedent
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    for (const emoji of txt.match(emojiRegex) ?? []) {
      process.stdout.write(`${emoji}\n`);
    }
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - txt-emoji-count

program.command("txt-emoji-count").description("txt-emoji-count description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-emoji-count"] = async function (file: string | undefined, opts: {}) {
  // TODO: dedent
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
};

// -----------------------------------------------------------------------------
// command - txt-extrace-prettify

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

program.command("txt-extrace-prettify")
  .description("prettify `sudo extrace -tu | ts` output")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-extrace-prettify"] = async function (file: string | undefined, opts: {}) {
  // TODO: dedent
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
};

// -----------------------------------------------------------------------------
// command - txt-file-backup-sha1-hash-analyze

program.command("txt-file-backup-sha1-hash-analyze").description("txt-file-backup-sha1-hash-analyze description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-file-backup-sha1-hash-analyze"] = async function (file: string | undefined, opts: { grep?: string, merge?: string, sortLen: boolean }) {
  // TODO: dedent
    const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    const sha1Paths: { [key: string]: string[] } = {};
    for (const line of txt.split(/\r?\n/)) {
      const match = /^([^-].*)  ([0-9a-f]{16})$/.exec(line);
      if (match === null) {
        if (!line.startsWith("-") && line.trim() !== "") {
          console.warn(`ignore line: ${line}`);
        }
        continue;
      }
      sha1Paths[match[2]] = sha1Paths[match[2]] ?? [];
      sha1Paths[match[2]].push(match[1]);
    }
    for (const line of txt.split(/\r?\n/)) {
      if (!line.startsWith("-")) continue;
      const match = /^-(.+)  ([0-9a-f]{16})$/.exec(line);
      if (match === null) {
        console.warn(`ignore line: ${line}`);
        continue;
      }
      if (match[2] in sha1Paths) {
        console.log(`${line} -> ${sha1Paths[match[2]].join(", ")}`);
      } else {
        console.log(`${line} -> __REAL_REMOVED__`);
      }
    }
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - txtFishHistoryEdit

program.command("txtFishHistoryEdit").description("txtFishHistoryEdit description")
  .addOption(new commander.Option("--grep <pattern>").conflicts(["merge", "sort-len"]))
  .addOption(new commander.Option("--merge <file>").conflicts(["grep", "sort-len"]))
  .addOption(new commander.Option("--sort-len").conflicts(["grep", "merge"]).default(false))
  .addArgument(new commander.Argument("[file]"))
  .action(txtFishHistoryEdit);

async function txtFishHistoryEdit(file: string | undefined, opts: { grep?: string, merge?: string, sortLen: boolean }) {
  const txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");

  // wsh79 Ubuntu 22.04: # 2006年01月02日 15時04分05秒
  // wsh24 Ubuntu 24:04: # Mon 02 Jan 2006 03:04:05 PM JST
  const re = /^# (?<date>(?<date79>(?<year>\d{4})年(?<month79>\d\d)月(?<day79>\d\d)日 (?<hour79>\d\d)時(?<min79>\d\d)分(?<sec79>\d\d)秒)|(?<date24>(?<_weekdayStr>\w{3}) (?<day24>\d\d) (?<monthStr24>\w{3}) (?<year24>\d{4}) (?<hour24_12>\d\d):(?<min24>\d\d):(?<sec24>\d\d) (?<ampm24>AM|PM) (?<_tz24>\w{3})))(\r?\n)(?<cmd>[\s\S]+?)((?=\r?\n(# \w{3} \d\d \w{3} \d{4} \d\d:\d\d:\d\d (AM|PM) \w{3}|$))|(?=\r?\n(# \d{4}年\d\d月\d\d日 \d\d時\d\d分\d\d秒|$)))/gm;

  const match__ = (txt: string): (RegExpExecArray & { groups: { [key: string]: string } })[] => {
    const matches = [...txt.matchAll(re)] as (RegExpExecArray & { groups: { [key: string]: string } })[];
    for (const match of matches) {
      if (match.groups.date24 !== undefined) {
        match.groups.month = ("JanFebMarAprMayJunJulAugSepOctNovDec".indexOf(match.groups.monthStr) / 3 + 1).toString().padStart(2, "0");
        match.groups.hour = (Number(match.groups.hour12) + (match.groups.ampm === "PM" ? 12 : 0)).toString().padStart(2, "0");
      }
      // @ts-expect-error
      match._date = new Date(`${match.groups.year}-${match.groups.month}-${match.groups.day}T${match.groups.hour}:${match.groups.min}:${match.groups.sec}`);
    }
    return matches;
  }

  const matches = match__(txt);
  if (matches.length === 0) {
    logger.warn(`not matched to: ${re}`);
    return cliCommandExit(1);
  }

  if (opts.grep !== undefined) {
    for (const match of matches) {
      if (!new RegExp(opts.grep).test(match.groups.cmd)) continue;
      process.stdout.write(`${match[0]}\n`);
    }
    return cliCommandExit(0);
  }

  if (opts.merge !== undefined) {
    const set = new Set(matches.map((match) => JSON.stringify({ date: match.groups.date, cmd: match.groups.cmd })));
    const txt2 = fs.readFileSync(opts.merge, "utf8");
    const matches2 = match__(txt2);
    const set2 = new Set(matches2.map((match) => JSON.stringify({ date: match.groups.date, cmd: match.groups.cmd })));
    const mergedSet = new Set([...set, ...set2]);
    const mergedArr = [...mergedSet];
    mergedArr.sort((a, b) => a.localeCompare(b));
    for (const j of mergedArr.reverse()) {
      const json = JSON.parse(j);
      process.stdout.write(`# ${json.date}\n${json.cmd}\n`);
    }
    return cliCommandExit(0);
  }

  if (opts.sortLen) {
    for (const match of matches.toSorted((a, b) => a.groups.cmd.length - b.groups.cmd.length)) {
      process.stdout.write(`# ${match.groups.date} ${Buffer.from(match.groups.cmd).toString("base64")}\n${match.groups.cmd}\n`);
    }
    return cliCommandExit(0);
  }

  // create edit file

  const cmdLenMax = Math.max(...matches.map((match) => match.groups.cmd.length));
  const matchesNoNL: RegExpMatchArray[] = [];
  // exclude \n
  for (const match of matches) {
    if (match.groups.cmd?.includes("\n")) {
      logger.warn(`ignore command with newline: ${match.groups.cmd}`);
    }
    matchesNoNL.push(match);
  }
  for (const match of matches) {
    process.stdout.write(`${match.groups.cmd.padEnd(cmdLenMax, " ")} #__date__ ${match.groups.date} __b64__ ${Buffer.from(match.groups.cmd as string).toString("base64")}\n`);
  }

  return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - txtFishHistMerge

/*
Merge several ~/.local/share/fish/fish_history files.

format:
- cmd: git checkout ./
  when: 1736769788
  paths:
    - ./
(`paths` is optional)

# no diff
c.js txtFishHistMerge ~/.local/share/fish/fish_history >/tmp/fish_history_merged && delta ~/.local/share/fish/fish_history /tmp/fish_history_merged
*/

program.command("txtFishHistMerge").description("txtFishHistMerge description")
  .addArgument(new commander.Argument("<file...>"))
  .action((file, opts) => txtFishHistMerge(file, { _cli: true, ...opts }));

async function  txtFishHistMerge(
  file: string[],
  opts: {
    _cli?: boolean,
  },
) {
  const pairsFileTxt = file.map((file) => {
    if (file === "-") {
      logger.debug(`read from stdin`);
      file = "/dev/stdin";
    }
    const txt = fs.readFileSync(file, "utf8");
    logger.debug(`${file}: ${txt.length} bytes`);
    return { file, txt };
  });

  const hists: { file: string, hist: string, cmd: string, when: number, paths?: string[] }[] = [];
  for (const { file, txt } of pairsFileTxt) {
    logger.debug(`${file}: ${txt.length} bytes`);
    const re = /^- cmd: (?<cmd>.+)(\r?\n)  when: (?<when>\d+)(\r?\n)(  paths:(\r?\n)(?<paths>(    - .+(\r?\n))+))?/gm;
    const matches = [...txt.matchAll(re)] as (RegExpExecArray & { groups: { [key: string]: string } })[];
    logger.debug({ file, length: txt.length, matches: matches.length });
    let whenPrev = 0;
    for (const match of matches) {
      const hist = match[0];
      // cmd
      // when
      const when = parseInt(match.groups.when);
      if (when < whenPrev) {
        // reaches sometimes
        logger.warn(`${file}: ${whenPrev} > ${when}; in:\n${hists.at(-1)!.hist}${hist}----------`);
      }
      whenPrev = when;
      // paths
      const paths = match.groups.paths === undefined ? [] : [...match.groups.paths.matchAll(/    - (.+)(\r?\n)/g)].map((m) => m[1]);
      //
      hists.push({ file, hist, cmd: match.groups.cmd, when, paths });
    }
    bp();
  }
  // sort by when
  hists.sort((a, b) => a.when - b.when);
  process.stdout.write(`${hists.map((hist) => hist.hist).join("")}`);
  return cliCommandExit(0);
}

// -----------------------------------------------------------------------------
// command - txtGitDiffPatch

program.command("txtGitDiffPatch").description("txtGitDiffPatch description")
  .addArgument(new commander.Argument("<patchPathA>"))
  .addArgument(new commander.Argument("<patchPathB>"))
  .action((...args) => txtGitDiffPatch(...args, true));

async function txtGitDiffPatch(
  patchPathA: string,
  patchPathB: string,
  opts?: {},
  command?: commander.Command<unknown[]>,
  _cli?: true,
): Promise<void> {
  const patchA = fs.readFileSync(patchPathA, "utf8");
  const patchB = fs.readFileSync(patchPathB, "utf8");
  process.stdout.write(await txtGitDiffPatchStr(patchA, patchB));
  return cliCommandExit(0);
}

async function txtGitDiffPatchStr(
  patchA: string,
  patchB: string,
  opts?: {},
): Promise<string> {
  const Diff = await import("diff");
  let patch = Diff.createPatch("__filename__", patchA, patchB);
  return patch;
}

// -----------------------------------------------------------------------------
// command - txt-html-break

// abort

program.command("txt-html-break").description("txt-html-break description")
  .addOption(new commander.Option("--z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-html-break"] = async function (file: string | undefined, opts: { zTest: boolean }) {
  // TODO: dedent
    if (opts.zTest) {
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
};

function txtHTMLBreak(html: string): string {
  html = txtHTMLCDataB64(html);
  while ((reArr = /^(\S)(<\w+>)/m.exec(html)) !== null) {
    html = html.replace(reArr[0], `${reArr[1]}\n${reArr[2]}`);
  }
  html = txtHTMLCDataB64d(html);
  return html;
}

function txtHTMLBreakOld(html: string): string {
  const offsets = [{offset: -1, kind: "dummy"}];
  // @ts-expect-error
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
      // @ts-expect-error
      assert(node.sourceCodeLocation.startOffset >= offsets.at(-1).offset);
      offsets.push({offset: node.sourceCodeLocation.startOffset, kind: `|${node.nodeName}`});
    }
    if (("childNodes" in node)) {
      for (const n of node.childNodes) {
        dig(n);
      }
    }
    if ("sourceCodeLocation" in node && node.sourceCodeLocation !== null) {
      // @ts-expect-error
      assert(node.sourceCodeLocation.endOffset >= offsets.at(-1).offset);
      offsets.push({ offset: node.sourceCodeLocation.endOffset, kind: `${node.nodeName}|` });
    }
  }
  html = txtHTMLCDataB64(html); // without this: <![CDATA[>]]> is treated as "<!-- [CDATA[ -->" and "]]>"
  const parse5 = require("parse5");
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
// command - txt-html-cdata-b64

program.command("txt-html-cdata-b64").description("txt-html-cdata-b64 description")
  .addOption(new commander.Option("--z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-html-cdata-b64"] = async function (file: string | undefined, opts: { zTest: boolean }) {
  // TODO: dedent
    if (opts.zTest) {
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
};

function txtHTMLCDataB64(html: string): string {
  for (const match of html.matchAll(/<!\[CDATA\[[\s\S]*?]]>/g)) {
    html = html.replace(match[0], `<CDATA>${Buffer.from(match[0]).toString("base64")}</CDATA>`);
  }
  return html;
}

// -----------------------------------------------------------------------------
// command - txt-html-cdata-b64d

program.command("txt-html-cdata-b64d").description("txt-html-cdata-b64d description")
  .addOption(new commander.Option("--z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-html-cdata-b64d"] = async function (file: string | undefined, opts: { zTest: boolean }) {
  // TODO: dedent
    if (opts.zTest) {
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
};

function txtHTMLCDataB64d(html: string): string {
  for (const match of html.matchAll(/<CDATA>(.+?)<\/CDATA>/g)) {
    html = html.replace(match[0], regExpReplacerEscape(`${Buffer.from(match[1], "base64").toString("utf8")}`));
  }
  return html;
}

// -----------------------------------------------------------------------------
// command - txt-json-flatten

program.command("txt-json-flatten").description("txt-json-flatten description")
  .addOption(new commander.Option("--width <number>").default(80).argParser(CLI.parseIntPort))
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-json-flatten"] = async function (file: string | undefined, opts: { width: number }) {
  // TODO: dedent
    const flat = strJSONFlat("", JSON.parse(fs.readFileSync(file ?? "/dev/stdin", "utf8")), { width: opts.width });
    process.stdout.write(`${flat.join("\n")}\n`);
    return cliCommandExit(0);
};

function strJSONFlat(key: string, j: unknown, opts: { width: number }): string[] {
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
    return [...j.entries()].map(([i, value]) => strJSONFlat(`${key}[${i}]`, value, opts)).flat();
  }
  assert.ok(j !== undefined && j.constructor === Object);
  if (Object.keys(j).length === 0) {
    return key === "" ? ["{}"] : [`${key}: {}`];
  }
  // return Object.entries(j).map(([key, value]) => `.${key}: ${strJSONFlat(value, {width: opts.width - key.length - 3 /* .:SPACE */})}`);
  return Object.entries(j).map(([thisKey, value]) => strJSONFlat(`${key}.${thisKey}`, value, opts)).flat();
}

// -----------------------------------------------------------------------------
// command - txtMarkdownCat
// [@cat](file://PATH) -> <PATH content>
// [@cat:@beg:SECTION](file://PATH) -> <PATH: @beg:SECTION...@end:SECTION>
// [@cat:@sec:SECTION](file://PATH) -> <PATH: ## ... @sec:SECTION ...>

program.command("txtMarkdownCat").description("txtMarkdownCat description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txtMarkdownCat"] = async function (
  file: string | undefined,
  opts: {
  },
) {
  process.stdout.write(txtMarkdownCat(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
  return cliCommandExit(0);
}

export function txtMarkdownCat(txt: string): string {
  while ((reArr = /\[@cat]\(file:\/\/(?<path>[^)]+)\)/.exec(txt)) !== null) {
    const { path } = reArr.groups as { path: string };
    txt = txt.replace(reArr[0], regExpReplacerEscape(strRemoveLastLine(fs.readFileSync(path, "utf8"))));
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
    // @ts-expect-error
    txt = txt.replace(reArr[0], regExpReplacerEscape(reArr1.groups.body));
  }

  return txt;
}

// -----------------------------------------------------------------------------
// command - txtMarkdownCodeB64

/*
```sh
code
```
-> @__code_block__:YGBgc2gKY29kZQpgYGA=
*/

program.command("txtMarkdownCodeB64").description("txtMarkdownCodeB64 description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txtMarkdownCodeB64"] = async function (file: string | undefined, opts: {}) {
  process.stdout.write(txtMarkdownCodeB64(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
  return cliCommandExit(0);
};

export function txtMarkdownCodeB64(txt: string): string {
  for (const match of txt.matchAll(/^```(\w+)?[\s\S]+?^```$/gm)) {
    const b64 = Buffer.from(match[0]).toString("base64");
    txt = txt.replace(match[0], `@__code_block__:${b64}`);
  }
  return txt;
}

// -----------------------------------------------------------------------------
// command - txtMarkdownCodeB64d

program.command("txtMarkdownCodeB64d").description("txtMarkdownCodeB64d description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txtMarkdownCodeB64d"] = async function (file: string | undefined, opts: {}) {
  process.stdout.write(txtMarkdownCodeB64d(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
  return cliCommandExit(0);
};

export function txtMarkdownCodeB64d(txt: string): string {
  for (const match of txt.matchAll(/^@__code_block__:(.+)$/gm)) {
    const b64 = match[1];
    const code = Buffer.from(b64, "base64").toString("utf8");
    txt = strReplace(txt, match[0], code);
  }
  return txt;
}

// -----------------------------------------------------------------------------
// command - txt-markdown-h2-sec

program.command("txt-markdown-h2-sec").description("txt-markdown-h2-sec description")
  .addOption(new commander.Option("--z-test").default(false).hideHelp())
  .addArgument(new commander.Argument("<section>", "## @sec:<section>"))
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-markdown-h2-sec"] = async function (section: string, file: string | undefined, opts: { zTest: boolean }) {
  // TODO: dedent
    if (opts.zTest) {
      section = "SEC";
      file = `${DIR_TMP}/test-txt-markdown-h2-sec.txt`;
      fs.writeFileSync(file, txtMarkdownH2SecTestIn);
    }
    let txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    txt = txtMarkdownCodeB64(txt);
    const matches = [...txt.matchAll(new RegExp(`(?<=(^|\\r?\\n))(?<txt>## .*@sec:${section}\\b[\\s\\S]+?)(?=\r?\n## |\\$)`, "g"))];
    txt = matches.map((match) => match.groups?.txt).join("\n");
    txt = txtMarkdownCodeB64d(txt);
    if (opts.zTest) {
      assert.strictEqual(txt, txtMarkdownH2SecTestOut);
      return cliCommandExit(0);
    }
    process.stdout.write(txt);
    return cliCommandExit(0);
};

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
// command - txtMarkdownH2SectionReduce

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

program.command("txtMarkdownH2SectionReduce").description("txtMarkdownH2SectionReduce description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txtMarkdownH2SectionReduce"] = async function (file: string | undefined, opts: {}) {
  process.stdout.write(txtMarkdownH2SectionReduce(fs.readFileSync(file ?? "/dev/stdin", "utf8")));
  return cliCommandExit(0);
}

export function txtMarkdownH2SectionReduce(txt: string): string {
  // TODO: dedent
    const nCommonElementsFromTheBeginning = (arr1: string[], arr2: string[]) => [...arr1, "\0dummy\0"].findIndex((tok, i) => tok !== arr2[i]);
    let tokensStack: string[] = []; // ## z1 - z2 - z3 -> ["z1", "z2", "z3"]
    let txt2 = "";
    let xxx_workAround_seemsExtraLineAdded_testsNeeded = false;
    for (const line of txt.split(/\r?\n/)) {
      if (!line.startsWith("## ")) {
        txt2 += `${line}\n`;
        continue;
      }
      const tokens = line.slice("## ".length).split(" - ");
      const nAlreadyPrintedTokens = nCommonElementsFromTheBeginning(tokensStack, tokens);
      for (let level = nAlreadyPrintedTokens; level < tokens.length; level++) {
        txt2 += `##${"#".repeat(level)} ${tokens[level]}\n`;
        if (level !== tokens.length - 1) {
          xxx_workAround_seemsExtraLineAdded_testsNeeded = true;
          txt2 += "\n";
        }
      }
      tokensStack = tokens;
    }
    if (xxx_workAround_seemsExtraLineAdded_testsNeeded) {
      txt2 = txt2.slice(0, -1);
    }
    return txt2;
};

// -----------------------------------------------------------------------------
// command - txt-markdown-headers

program.command("txt-markdown-headers").description("txt-markdown-headers description")
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-markdown-headers"] = async function (file: string | undefined, opts: {}) {
  // TODO: dedent
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
      const line1 = parseInt(reArr[1]);
      const line2 = parseInt(reArr[2]);
      assert.deepStrictEqual(line1 + 1, line2);
      return line1;
    });
    child_process.execSync(`sed -n 1,2p`, { encoding: "utf8", input: txt, maxBuffer: 2 ** 26 });
    child_process.execSync(`sed -n -e ${lineNums.join("p -e ")}p`, { encoding: "utf8", input: txt, maxBuffer: 2 ** 26, stdio: ["pipe", "inherit", "inherit"] });

    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - txtPrivate

program.command("txtPrivate").alias(/*compatibility*/"txt-private").description("txtPrivate description")
  .addOption(new commander.Option("--preserve-plp").default(false))
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txtPrivate"] = async function (file: string | undefined, opts: { preservePlp: boolean }) {
  const txt = file ? fs.readFileSync(file, "utf8") : await (async () => {
    logger.info(`reading from stdin...`);
    return await readStdin();
  })();
  logger.info(`txt.length: ${txt.length}`);
  process.stdout.write(txtPrivate(txt, opts));
  return cliCommandExit(0);
}

export function txtPrivate(txt: string, opts?: { preservePlp?: boolean }): string {
  opts ??= {};
  opts.preservePlp ??= false;
  // @ bv ... @ ev
  txt = txt.replaceAll(/^.*@(bv)\b.*(\r?\n)[\s\S]*?@(ev)\b.*(\r?\n|$)/gm, "");

  // @ pl private line
  while ((reArr = /^.*@(pl)\b.*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");
  // @ pla private line above
  while ((reArr = /^.*(\r?\n).*@(pla)\b.*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");
  // @ plb private line below
  while ((reArr = /^.*@(plb)\b.*(\r?\n).*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");
  // @ plr private line right and comment (# //)
  while ((reArr = /\s*(#|\/\/)\s*@(plr)\b.*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");
  // @ plr private line right
  while ((reArr = /\s*@(plr)\b.*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");

  // @ *p (@* publish)
  if (!opts.preservePlp) {
    // @ bvp ... @ evp
    txt = txt.replaceAll(/^.*@(bvp)\b.*(\r?\n)[\s\S]*?@(evp)\b.*(\r?\n|$)/gm, "");

    // @ plp private line, publish
    while ((reArr = /^.*@(plp)\b.*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");
    // @ plap private line above, publish
    while ((reArr = /^.*(\r?\n).*@(plap)\b.*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");
    // @ plbp private line below, publish
    while ((reArr = /^.*@(plbp)\b.*(\r?\n).*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");
    // @ plrp private line right and comment (# //), publish
    while ((reArr = /\s*(#|\/\/)\s*@(plrp)\b.*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");
    // @ plrp private line right, publish
    while ((reArr = /\s*@(plrp)\b.*(\r?\n|$)/m.exec(txt)) !== null) txt = txt.replace(reArr[0], "");
  }

  return txt;
};

// -----------------------------------------------------------------------------
// command - txt-regexp-search (re)

/*
echo -e "foo\nbar" | c.js -q re -f m '^\w+$'                                     # [["foo"],["bar"]]
echo -e "foo\nbar" | c.js -q re -f m '^((\w)(\w+))$'                             # [["foo","foo","f","oo"],["bar","bar","b","ar"]]
echo -e "foo\nbar" | c.js -q re -f m '^(?<word>(?<head>\w)(?<tail>\w+))$'        # [{"word":"foo","head":"f","tail":"oo"},{"word":"bar","head":"b","tail":"ar"}]
echo -e "foo\nbar" | c.js -q re -f i '^(?<word>(?<head>\w)(?<tail>\w+))$'        # not match with /^(?<word>(?<head>\w)(?<tail>\w+))$/gi

echo -e "foo\nbar" | node -e 'console.log(fs.readFileSync("/dev/stdin", "utf8").match(new RegExp(process.argv[1], "m"))[0]);' '^foo$'
echo -e "foo\nbar" | node -e 'console.log(fs.readFileSync("/dev/stdin", "utf8").match(new RegExp(process.argv[1], process.argv[2] ?? "m"))[0]);' '^foo$' "m"
*/

program.command("txt-regexp-search").alias("re").description("txt-regexp-search description")
  .addOption(new commander.Option("-f, --flags <flags>").default("m"))
  .addArgument(new commander.Argument("<pattern>"))
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-regexp-search"] = async function (pattern: string, file: string | undefined, opts: { flags: string }) {
  // TODO: dedent
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
};

// -----------------------------------------------------------------------------
// command - txt-replace (rep)

program.command("txt-replace").alias("rep").description("txt-replace description")
  .addOption(new commander.Option("-m, --max-count <num>").argParser(CLI.parseIntPositive))
  .addOption(new commander.Option("-r, --regexp").default(false))
  .addOption(new commander.Option("-f, --regexp-flags <flags>").default("gm").implies({ regexp: true }))
  .addArgument(new commander.Argument("from"))
  .addArgument(new commander.Argument("to"))
  .addArgument(new commander.Argument("[file]"))
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["txt-replace"] = async function (from: string, to: string, file: string | undefined, opts: { maxCount?: number, regexp: boolean, regexpFlags: string }) {
  // TODO: dedent
    let txt = fs.readFileSync(file ?? "/dev/stdin", "utf8");
    const from2 = opts.regexp ? new RegExp(from, opts.regexpFlags) : from;
    opts.maxCount ??= Infinity;
    txt = txt.replaceAll(from2, (substring, ...args) => {
      // @ts-expect-error
      if (opts.maxCount-- <= 0) return substring;
      return to;
    });
    process.stdout.write(txt);
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// command - txtSortSection

/*
sort:

--type=c.ts :
// ----------... (to column 80)
// command - {NAME}
(contents)

--type=scrap.ts :
// ----------... (to column 80)
// {NAME}
(contents)
*/

program.command("txtSortSection").alias("sec").description("txtSortSection description")
  .addArgument(new commander.Argument("[file]"))
  .addOption(new commander.Option("--type <type>").choices(["c.ts", "scrap.ts"]).makeOptionMandatory(true))
  .action(async (file, opts) => {
    const txt = file ? fs.readFileSync(file, "utf8") : await (async () => {
      logger.info(`reading from stdin...`);
      return await readStdin();
    })();
    logger.info(`txt.length: ${txt.length}`);
    const txt2 = txtSortSection(txt, opts);
    process.stdout.write(txt2);
    return cliCommandExit(0);
  });

export function txtSortSection(
  txt: string,
  opts: {
    type?: string;
  },
): string {
  let separator: RegExp;
  if (opts.type === "c.ts") {
    [...txt.matchAll(new RegExp(`^// ${"-".repeat(77)}(\r?\n)// command - (?<name>[\\w-]+).*$`, "gm"))]; // eslint-disable-line @typescript-eslint/no-unused-expressions
    [...txt.matchAll(reReplaceAll(/^\/\/ ---(\r?\n)\/\/ command - (?<name>[\w-]+).*$/gm, "---", "-".repeat(77)))]; // eslint-disable-line @typescript-eslint/no-unused-expressions
    separator = new RegExp(`^// ${"-".repeat(77)}(\r?\n)// command - (?<name>[\\w-]+).*$`, "gm");
  }
  if (opts.type === "scrap.ts") {
    separator = new RegExp(`^// ${"-".repeat(77)}(\r?\n)// (?<name>.+)$`, "gm");
  }

  // @ts-expect-error
  assert.ok(separator !== undefined);
  const matches = [...txt.matchAll(separator)] as (RegExpExecArray & { groups: { [key: string]: string }, index: number })[];
  if (matches.length === 0) {
    logger.warn(`not match with: ${separator}`);
    return txt;
  }
  const prologue = txt.slice(0, matches[0].index);
  // const lastSection = txt.slice(matches.at(-1)!.index);
  let txt2 = txt.slice(0, matches[0].index);
  const sections: { name: string, nameRaw: string, index: number, txt: string }[] = matches.slice(0, -1).map((_, i) => {
    const match = matches[i];
    const matchNext = matches[i + 1];
    return {
      name: match.groups.name.replaceAll("-", "").toLowerCase(),
      nameRaw: match.groups.name,
      index: match.index,
      txt: txt.slice(match.index, matchNext.index)
    };
  });
  sections.push({ name: matches.at(-1)!.groups.name.replaceAll("-", "").toLowerCase(), nameRaw: matches.at(-1)!.groups.name, index: matches.at(-1)!.index, txt: txt.slice(matches.at(-1)!.index) });
  sections.toSorted((a, b) => a.name.localeCompare(b.name)).forEach((section) => {
    txt2 += section.txt;
  });
  return txt2;
}

// -----------------------------------------------------------------------------
// command - z-meta-command-list

program.command("z-meta-command-list")
  .description("meta command - list subcommands")
  // @ts-expect-error
  .action((...args) => cliCmds[args.at(-1).name()](...args));

cliCmds["z-meta-command-list"] = async function (opts: {}) {
  // TODO: dedent
    const names = program.commands.map((command) => command.name());
    process.stdout.write(`${names.join("\n")}\n`);
    return cliCommandExit(0);
};

// -----------------------------------------------------------------------------
// main

// https://stackoverflow.com/questions/45136831/node-js-require-main-module/60309682#60309682
if (esMain(import.meta) && !process.env.CTS_TEST_CLI) {
  await cliMain();
}

// import whyIsNodeRunning from "why-is-node-running";
// whyIsNodeRunning();
