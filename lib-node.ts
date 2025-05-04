// SPDX-FileCopyrightText: Copyright (c) 2024-2025 Wataru Ashihara <wataash0607@gmail.com>
// SPDX-License-Identifier: Apache-2.0

import * as assert from "node:assert/strict";
import * as child_process from "node:child_process";
import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as fsPromises from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";
import * as timersPromises from "node:timers/promises";
import * as url from "node:url";
import * as util from "node:util";

import * as commander from "@commander-js/extra-typings";

import * as lib from "./lib.js";
import { MyError } from "./lib.js";
import type { Logger } from "./logger.js";

export class CLI {
  #commandExitResolvers: PromiseWithResolvers<number>;

  constructor() {
    this.#commandExitResolvers  = Promise.withResolvers<number>();
  }

  async main(program_: commander.Command, myErrorClass: new (...args: any[]) => Error, logger: Logger): Promise<void> {
    try {
      await program_.parseAsync(process.argv);
      process.exitCode = await this.#commandExitResolvers.promise;
      assert.ok(process.exitCode !== undefined);
      return;
    } catch (e) {
      if (!(e instanceof myErrorClass)) {
        logger.error(`unexpected error: ${e}`);
        throw e;
      }
      // assert.ok(e.constructor.name === "MyError")
      logger.error(e.message);
      if (process.exitCode === undefined) {
        process.exitCode = 1;
      }
      return;
    }
    lib.unreachable();
  }

  commandExit(exitCode: number): void {
    this.#commandExitResolvers.resolve(exitCode);
  }

  // static

  static argCheck(value: string, cond: boolean, errMsg: string): string {
    if (!cond) throw new commander.InvalidArgumentError(errMsg);
    return value;
  }

  static invalidArgument(errMsg: string): never {
    throw new commander.InvalidArgumentError(errMsg);
  }


  // https://github.com/tj/commander.js#custom-option-processing

  static parseDuration(value: string, dummyPrevious?: number): number {
    if (value.match(/^\d+$/)) return parseInt(value);
    const cmd = `date -d ${lib.Str.escapeShell(`19700101 ${value}`)} -u +%s`;
    const secs = parseInt(CP.shSync(cmd));
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

export class CP {
  static async sh(cmd: string, execOptions: Omit<child_process.ExecOptionsWithStringEncoding, "encoding"> = {}): Promise<string> {
    return util.promisify(child_process.exec)(cmd, { encoding: "utf8", ...execOptions }).then(({ stdout, stderr }) => {
      // if (stderr !== "") logger.error(`stderr: ${stderr}`.replace(/(\r?\n)$/, "⏎"));
      return stdout;
    });
  }

  static shSync(cmd: string, execSyncOptions: Omit<child_process.ExecSyncOptionsWithStringEncoding, "encoding"> = {}): string {
    return child_process.execSync(cmd, { encoding: "utf8", ...execSyncOptions });
  }

  static async testSh() {
    let tmp;
    tmp = this.shSync(`echo {}; echo err >&2`); // err: direct stderr
    tmp = await this.sh(`echo {}; echo err >&2`); // err: logger.error()
    "breakpoint".match(/breakpoint/);
  }

  // TODO: test: file names including whiltespaces
  shGlob(expr: string): string[] {
    return child_process.execSync(`echo ${expr}`, { encoding: "utf8" }).replace(/\r?\n$/, "").split(" ");
  }
}

export class FS {
  static async jsonParsePath(path: string): Promise<ReturnType<typeof JSON.parse>> {
    try {
      return JSON.parse(await fsPromises.readFile(path, "utf8"));
    } catch (e) {
      if (!(e instanceof SyntaxError)) throw e;
      e.message = `invalid JSON: ${path}: ${e.message}`;
      throw e;
    }
  }

  static jsonParsePathSync(path: string): ReturnType<typeof JSON.parse> {
    try {
      return JSON.parse(fs.readFileSync(path, "utf8"));
    } catch (e) {
      if (!(e instanceof SyntaxError)) throw e;
      e.message = `invalid JSON: ${path}: ${e.message}`;
      throw e;
    }
  }

  // ln -f existingPath newPath (creates/overwrites newPath)
  static lnF(existingPath: string, newPath: string, workDir: string) {
    const randomPath = `${workDir}/${crypto.randomBytes(8).toString("hex")}`;
    fs.linkSync(existingPath, randomPath); // fails if randomPath exists
    fs.renameSync(randomPath, newPath);
  }

  // ln -fs existingPath newPath (creates/overwrites newPath)
  static lnFS(existingPath: string, newPath: string, workDir: string) {
    const randomPath = `${workDir}/${crypto.randomBytes(8).toString("hex")}`;
    fs.symlinkSync(existingPath, randomPath); // fails if randomPath exists
    fs.renameSync(randomPath, newPath);
  }
}

// @deprecated
export function jsonParsePathSync(path: string): ReturnType<typeof JSON.parse> {
  return FS.jsonParsePathSync(path);
}
if (0) {
  jsonParsePathSync(`/etc/hosts`);
  lib.unreachable();
}

// let logger: Logger;
// if (typeof process === "object") {
//   logger = new Logger();
// }
// export function setLogger(logger_: Logger): void {
//   logger = logger_;
// }
