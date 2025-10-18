#!/usr/bin/env node
// SPDX-FileCopyrightText: Copyright (c) 2022-2025 Wataru Ashihara <wataash0607@gmail.com>
// SPDX-License-Identifier: Apache-2.0

/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/no-unused-expressions */
/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable no-constant-condition */
/* eslint-disable no-debugger */
/* eslint-disable no-regex-spaces */

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
...
*/

import * as assert from "node:assert/strict";
import * as child_process from "node:child_process";
import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as fsPromise from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";
import * as readline from "node:readline/promises";
import * as url from "node:url";
import * as util from "node:util";

import * as commander from "@commander-js/extra-typings";
import envPaths from "env-paths";
import esMain from "es-main";
import type express from "express";
import type pty_ from "node-pty";
import fetchSync from "sync-fetch";
const fetchSync_ = fetchSync; // avoid unused-removal

import { cliCommandExit, logger } from "./c.js";
import * as libNode from "./lib-node.js";
import { Logger } from "./logger.js";

const __filename = url.fileURLToPath(import.meta.url);
const program = new commander.Command();

// -----------------------------------------------------------------------------
// lib

import {
  AppError,
  bp,
  DIR_CACHE,
  DIR_TMP,
  ie,
  iie,
  iio,
  integersSummary,
  io,
  isObject,
  Queue,
  reExec,
  reExecThrowAppError,
  regExpEscape,
  regExpReplacerEscape,
  reReplace,
  reReplaceWithSpecial$,
  sh,
  sleep,
  sleepForever,
  strColsWhichAre,
  strCommandsToShC,
  strEmptify,
  strEmptifyFromIndex,
  strEmptifyUntilIndex,
  strEscapeCdata,
  strEscapeShell,
  strFirstLine,
  strNodeOptionsRemoveInspect,
  strNodeOptionsRemoveInspectEnv,
  strNumberOfLines,
  strParseSSV,
  StrParseSSVEntry,
  strRemoveFirstLine,
  strRemoveLastLine,
  strRemovePrefix,
  strRemoveSuffix,
  strReplace,
  strReplaceAll,
  strSnip,
  strTrimTrailingSlashes,
  TextLineDecoder,
  unreachable,
} from "./c.js";

import {
  txtMarkdownCat,
  txtPrivate,
  txtHTMLCDataB64,
  txtHTMLCDataB64d,
  txtMarkdownCodeB64d,
  txtMarkdownCodeB64,
  txtMarkdownH2SectionReduce,
} from "./c.js";
import { CLI } from "./lib-node.js";

// -----------------------------------------------------------------------------
// command

let cli: CLI;
if (esMain(import.meta) && !process.env.CTS_TEST_CLI) {
  cli = new CLI();
  setImmediate(async () => {
    await cli.main(program, AppError, logger);
    "breakpoint".match(/breakpoint/);
  });
}

// -----------------------------------------------------------------------------
// command - cflmd

program.command("cflmd").description("cflmd description")
  // .addOption(new commander.Option("--diff-cmd <cmd>").default("diff -u"))
  .addOption(new commander.Option("--user <user>", "Confluence user name (required)").env("CFLMD_USER").makeOptionMandatory(true))
  .addOption(new commander.Option("--token <token>", "Confluence API token or password (required)").env("CFLMD_TOKEN").makeOptionMandatory(true))
  .addOption(new commander.Option("--cache-secs-page <number>", "http GET cache seconds for pages").env("CFLMD_CACHE_SECS_PAGE").default(3600).argParser(CLI.parseInt))
  .addOption(new commander.Option("--cache-secs-img <number>", "http GET cache seconds for images").env("CFLMD_CACHE_SECS_IMG").default(86400 * 30).argParser(CLI.parseInt))
  .addOption(new commander.Option("--diff-cmd <cmd>").default("delta --paging=never"))
  .addOption(new commander.Option("--no-txtMarkdownH2SectionReduce"))
  .addOption(new commander.Option("--z-test-as-possible-without-network").default(false).hideHelp())
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
    diffCmd: string, // not shell-escaped
    txtMarkdownH2SectionReduce: boolean,
    zTestAsPossibleWithoutNetwork: boolean, // not used yet
  },
) {
  const diffCmdMaybeDangerous = opts.diffCmd;
  // @ts-expect-error
  delete opts.diffCmd;
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

  const match = reExecThrowAppError(/^<!--(\r?\n)\[(?<title>.+?)]\((?<url>.+)\)(\r?\n)/, txt);
  const { title, url } = match.groups!;
  const cflmdFile: CflmdFile = { path: file, title, url: cflmdParseURL(url) };

  const pagePromise = cflmdPageGet({ ...opts, cacheSecsPage: 0 /* force GET */ }, cflmdFile.url).then((page) => {
    if (cflmdFile.title !== page.title) {
      logger.info(`update title: (${page.title} -> ${cflmdFile.title})`);
    }
    return page;
  });

  txt = await cflmdProcess1MarkdownPreProcess({ file: cflmdFile, opts, pagePromise, txts });
  // cflmdWrite(txt, "1.prep.md", false);

  const txtTmp = await cflmdProcess2Pandoc0Ref({ file: cflmdFile, opts, pagePromise, txts });
  cflmdWrite0("2.pandoc0Ref.html", txtTmp);

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
  // https://github.com/kangax/html-minifier/issues/1161 without txtHTMLCDataB64 txtHTMLCDataB64d: minify(`<![CDATA[\n___]><-___]]>`) -> Error: Parse Error: <-___]]>
  txt = txtHTMLCDataB64d(minify(txtHTMLCDataB64(txt), { caseSensitive: true, collapseWhitespace: true, keepClosingSlash: true }));
  // <a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK>...</a> -> <ac:link ...>...</ac:link>
  txt = txt.replaceAll(/<a CFMD_HACK_NO_TRIM_SPACES_AROUND_AC_LINK>(.+?)<\/a>/g, "<ac:link>$1</ac:link>");

  cflmdWrite(txts, "4.minify.html", txt, true);
  // TODO: assert.ok(dom equal)

  txt = `title: ${title}\nurl: ${url}\n\n` + txt.replaceAll("><", ">\n<");
  txt = txt.replaceAll(" <ac:link>", "<ac:link>");  // reduce diff with remote.4.minify.html.pretty_maybe_invalid.html
  cflmdWrite(txts, "4.minify.html.pretty_maybe_invalid.html", txt, true);

  // remote
  {
    const page = await pagePromise;
    let txt = page.body.storage.value;
    cflmdWrite(txts, "remote.0.html", txt, false);

    // https://github.com/kangax/html-minifier/issues/1161 without txtHTMLCDataB64 txtHTMLCDataB64d: minify(`<![CDATA[\n___]><-___]]>`) -> Error: Parse Error: <-___]]>
    txt = txtHTMLCDataB64d(minify(txtHTMLCDataB64(txt), { caseSensitive: true, collapseWhitespace: true, keepClosingSlash: true }));
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
    cflmdWrite(txts, "remote.4.minify.html.pretty_maybe_invalid.html", txt, true);
  }

  // @__cflmd:macro_id:0000 -> set remote UUID (as possible)
  //
  // 4.minify.html
  // 4.minify.html.pretty_maybe_invalid.html
  // remote.4.minify.html
  // remote.4.minify.html.pretty_maybe_invalid.html
  // ↓
  // 5.macro_id.html
  // 5.macro_id.html.pretty_maybe_invalid.html
  {
    const macroIDMap: Record<string, string> = { "9999": `550e8400-e29b-41d4-a716-446655440000` };
    const Diff = await import("diff");
    let diff = Diff.createPatch("__filename__", fs.readFileSync(`${DIR_CACHE}/cflmd/last/4.minify.html.pretty_maybe_invalid.html`, "utf8"), fs.readFileSync(`${DIR_CACHE}/cflmd/last/remote.4.minify.html.pretty_maybe_invalid.html`, "utf8"));
    // -<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="@__cflmd:macro_id:0">
    // +<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="550e8400-e29b-41d4-a716-446655440000">
    let match;
    while ((match = diff.match(/^-.* ac:macro-id="@__cflmd:macro_id:(?<tmpID>\d+)".*(\r?\n)\+.* ac:macro-id="(?<uuid>[^"]+)"/m)) !== null) {
      assert.ok(match.groups !== undefined);
      macroIDMap[match.groups.tmpID] = match.groups.uuid;
      diff = diff.replace(`@__cflmd:macro_id:${match.groups.tmpID}`, `@__cflmd:macro_id:${match.groups.uuid}`);
    }
    let txt1 = fs.readFileSync(`${DIR_CACHE}/cflmd/last/4.minify.html`, "utf8");
    let txt2 = fs.readFileSync(`${DIR_CACHE}/cflmd/last/4.minify.html.pretty_maybe_invalid.html`, "utf8");
    for (const [tmpID, uuid] of Object.entries(macroIDMap)) {
      txt1 = txt1.replace(`ac:macro-id="@__cflmd:macro_id:${tmpID}"`, `ac:macro-id="${uuid}"`);
      txt2 = txt2.replace(`ac:macro-id="@__cflmd:macro_id:${tmpID}"`, `ac:macro-id="${uuid}"`);
    }
    fs.writeFileSync(`${DIR_CACHE}/cflmd/last/5.macro_id.html`, txt1);
    fs.writeFileSync(`${DIR_CACHE}/cflmd/last/5.macro_id.html.pretty_maybe_invalid.html`, txt2);
    cflmdMaybeWriteDiff(`${DIR_CACHE}/cflmd/last/4.minify.html`, `${DIR_CACHE}/cflmd/last/5.macro_id.html`, `${DIR_CACHE}/cflmd/last/5.macro_id.html.diff`);
    cflmdMaybeWriteDiff(`${DIR_CACHE}/cflmd/last/4.minify.html.pretty_maybe_invalid.html`, `${DIR_CACHE}/cflmd/last/5.macro_id.html.pretty_maybe_invalid.html`, `${DIR_CACHE}/cflmd/last/5.macro_id.html.pretty_maybe_invalid.html.diff`);
  }

  // diff
  {
    const out = child_process.execSync(`cmp -s ${DIR_CACHE}/cflmd/last/remote.4.minify.html.pretty_maybe_invalid.html ${DIR_CACHE}/cflmd/last/5.macro_id.html.pretty_maybe_invalid.html || echo "differ"`, { encoding: "utf8" });
    if (out === "") {
      logger.info("up-to-date");
      return cliCommandExit(0);
    }
    assert.match(out, /^differ(\r?\n)$/);
  }
  child_process.execSync(`${diffCmdMaybeDangerous} ${DIR_CACHE}/cflmd/last/remote.4.minify.html.pretty_maybe_invalid.html ${DIR_CACHE}/cflmd/last/5.macro_id.html.pretty_maybe_invalid.html || true`, { stdio: "inherit" });

  const page = await pagePromise;
  fs.copyFileSync(`${DIR_CACHE}/cflmd/last/5.macro_id.html`, `${DIR_CACHE}/cflmd/last/6.edit.html`);
  fs.copyFileSync(`${DIR_CACHE}/cflmd/last/5.macro_id.html.pretty_maybe_invalid.html`, `${DIR_CACHE}/cflmd/last/6.edit.html.pretty_maybe_invalid.html`);
  while (true) {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    try {
      const ans = await rl.question(`update? Yes/[No]/Edit/Reload (url: ${cflmdFile.url.urlConfluenceTop}${page._links.webui})`);
      if (ans.toLowerCase() === "y" || ans.toLowerCase() === "yes") {
        break;
      }
      if (ans.toLowerCase() === "n" || ans.toLowerCase() === "no") {
        logger.debug(`bye`);
        return cliCommandExit(0);
      }
      if (ans.toLowerCase() === "e" || ans.toLowerCase() === "edit" || ans.toLowerCase() === "r" || ans.toLowerCase() === "reload") {
        if (ans.toLowerCase() === "e" || ans.toLowerCase() === "edit") {
          logger.debug(`rl.close() to release SIGINT handler`);
          rl.close();
          // process.env.EDITOR ?? process.env.VISUAL ?? "vi" // https://github.com/git/git/blob/v2.49.0/editor.c
          child_process.execSync(`${process.env.EDITOR ?? process.env.VISUAL ?? "vi"} ${DIR_CACHE}/cflmd/last/6.edit.html`, { stdio: "inherit" });
        } else {
          logger.debug("reload");
        }
        {
          let txt = fs.readFileSync(`${DIR_CACHE}/cflmd/last/6.edit.html`, "utf8");
          txt = `title: ${title}\nurl: ${url}\n\n` + txt.replaceAll("><", ">\n<");
          txt = txt.replaceAll(" <ac:link>", "<ac:link>");  // reduce diff with remote.4.minify.html.pretty_maybe_invalid.html
          fs.writeFileSync(`${DIR_CACHE}/cflmd/last/6.edit.html.pretty_maybe_invalid.html`, txt);
        }
        cflmdMaybeWriteDiff(`${DIR_CACHE}/cflmd/last/5.macro_id.html`, `${DIR_CACHE}/cflmd/last/6.edit.html`, `${DIR_CACHE}/cflmd/last/6.edit.html.diff`);
        cflmdMaybeWriteDiff(`${DIR_CACHE}/cflmd/last/5.macro_id.html.pretty_maybe_invalid.html`, `${DIR_CACHE}/cflmd/last/6.edit.html.pretty_maybe_invalid.html`, `${DIR_CACHE}/cflmd/last/6.edit.html.pretty_maybe_invalid.html.diff`);
        child_process.execSync(`${diffCmdMaybeDangerous} ${DIR_CACHE}/cflmd/last/remote.4.minify.html.pretty_maybe_invalid.html ${DIR_CACHE}/cflmd/last/6.edit.html.pretty_maybe_invalid.html || true`, { stdio: "inherit" });
        continue;
      }
      logger.debug(`invalid choice: ${ans}`);
    } finally {
      logger.debug(`rl.close()`);
      rl.close();
    }
  }

  txt = fs.readFileSync(`${DIR_CACHE}/cflmd/last/6.edit.html`, "utf8");

  // <ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="@__cflmd:macro_id:0000">
  // -> <ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="UUID">
  {
    let match;
    while ((match = txt.match(/ac:macro-id="@__cflmd:macro_id:(?<tmpID>\d+)"/)) !== null) {
      // NOTE: if two macro IDs have the same value, the second one will be changed to a random UUID
      const uuid = crypto.randomUUID();
      assert.ok(match.groups !== undefined);
      logger.debug(`@__cflmd:macro_id:${match.groups.tmpID} -> ${uuid}`);
      txt = txt.replace(`@__cflmd:macro_id:${match.groups.tmpID}`, `${uuid}`);
    }
  }
  // ensure @cflmd does not exist
  {
    const matches = [...txt.matchAll(/@cflmd|@cfmd|@__cflmd\b/g)];
    if (matches.length !== 0) {
      const lines = matches.map((m) => `${m[0]}: ${txt.slice(m.index - 50, m.index + m[0].length + 50).replaceAll(/\r?\n/g, "⏎")}`);
      throw new AppError(`@cflmd|@cfmd|@__cflmd found:\n${lines.join("\n")}`);
    }
  }
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
  cache?: { path: string, validSecs?: { value: number, opt: string } }
}): Promise<any & { at: number, at2: string }> {
  const d = new Date();
  const now = Number(d); // Date.now()
  const now2 = d.toLocaleString("sv-SE");

  const jsonCache = (() => {
    if (opts.cache === undefined) return null;
    if (opts.cache.validSecs === undefined) return null;
    if (!fs.existsSync(opts.cache.path)) return null;
    const json = libNode.jsonParsePathSync(opts.cache.path);
    if (typeof json.at !== "number") {
      logger.warn(`${opts.cache.path}: invalid cache file: ".at": ${json.at}`);
      return null;
    }
    if (now - json.at > opts.cache.validSecs.value * 1000) {
      logger.debug(`cache expired: ${opts.cache.path} (${((now - json.at) / 1000).toFixed(1)}s ago > ${opts.cache.validSecs.value}s) (${opts.cache.validSecs.opt})`);
      return null;
    }
    logger.debug(`use cache: ${opts.cache.path} (${((now - json.at) / 1000).toFixed(1)}s ago <= ${opts.cache.validSecs.value}s) (${opts.cache.validSecs.opt})`);
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
  cache: { path: string, validSecs?: { value: number, opt: string } }
}): Promise<Buffer> {
  const d = new Date();
  const now = Number(d); // Date.now()
  const now2 = d.toLocaleString("sv-SE");

  const bufferCache = (() => {
    if (opts.cache === undefined) return null;
    if (opts.cache.validSecs === undefined) return null;
    if (!fs.existsSync(opts.cache.path)) return null;
    const stat = fs.statSync(opts.cache.path);
    if (now - stat.mtimeMs > opts.cache.validSecs.value * 1000) {
      logger.debug(`cache expired: ${opts.cache.path} (${((now - stat.mtimeMs) / 1000).toFixed(1)}s ago > ${opts.cache.validSecs.value}s) (${opts.cache.validSecs.opt})`);
      return null;
    }
    logger.debug(`use cache: ${opts.cache.path} (${((now - stat.mtimeMs) / 1000).toFixed(1)}s ago <= ${opts.cache.validSecs.value}s) (${opts.cache.validSecs.opt})`);
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
    cache: { path: `${DIR_CACHE}/cflmd/api/content/${page.id}.json.PUT` },
  }
  const json = await cflmdFetchJSON(`${file.url.urlConfluenceTop}/rest/api/content/${page.id}?expand=body.storage,space,version`, { method: "PUT", headers, body }, fetchJSONOpts);
  // update GET cache file
  {
    const fetchJSONOpts = {
      logFetch: logger.debug.bind(logger),
      cache: { path: `${DIR_CACHE}/cflmd/api/content/${json.id}.json` },
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
      cache: { path: `${DIR_CACHE}/cflmd/api/content/${urlParsed.id}.json`, validSecs: { value: opts.cacheSecsPage, opt: "--cache-secs-page/CFLMD_CACHE_SECS_PAGE" } }
    };
    const json = await cflmdFetchJSON(`${urlParsed.urlConfluenceTop}/rest/api/content/${urlParsed.id}?expand=body.storage,space,version`, { method: "GET", headers }, fetchJSONOpts);
    return json;
  } else {
    const fetchJSONOpts = {
      logFetch: logger.debug.bind(logger),
      // NOTE: spaceKey and webuiTitle may contain special characters so may cause errors
      cache: { path: `${DIR_CACHE}/cflmd/api/content/${urlParsed.spaceKey}/${urlParsed.webuiTitle}.json`, validSecs: { value: opts.cacheSecsPage, opt: "--cache-secs-page/CFLMD_CACHE_SECS_PAGE" } },
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
  if (args.opts.txtMarkdownH2SectionReduce) {
    name = "1.prep.5_h2.md"        ; txt = txtMarkdownH2SectionReduce(txt)                           ; cflmdWrite(args.txts, name, txt, true); // ## foo - bar -> ## foo ### bar
  }
  name = "1.prep.images.md"        ; txt = await cflmdProcess1MarkdownPreProcessImages(txt, args)    ; cflmdWrite(args.txts, name, txt, true); // ![alt](image.png)
  name = "1.prep.info.md"          ; txt = cflmdProcess1MarkdownPreProcessInfo(txt, args)            ; cflmdWrite(args.txts, name, txt, true); // <cflmd:info>
  name = "1.prep.misc.md"          ; txt = cflmdProcess1MarkdownPreProcessMisc(txt, args)            ; cflmdWrite(args.txts, name, txt, true); //
  name = "1.prep.toc.md"           ; txt = cflmdProcess1MarkdownPreProcessTOC(txt, args)             ; cflmdWrite(args.txts, name, txt, true); // @cflmd:toc
  name = "1.prep.z_code_b64d.md"   ; txt = txtMarkdownCodeB64d(txt)                                  ; cflmdWrite(args.txts, name, txt, true); //
  cflmdWrite(args.txts, "1.prep.preprocess.md", txt, true);

  return txt;
}

// remove: ## @cflmd:hidden
function cflmdProcess1MarkdownPreProcessCflmdHidden(txt: string, args: CflmdProcessArgs): string {
  txt = txt.replaceAll(/@cfmd:hidden\b/g, "@cflmd:hidden"); // compatibility
  txt = txt + "\0";
  // eslint-disable-next-line no-control-regex
  for (const match of txt.matchAll(/^## .*@cflmd:hidden\b.*$[\s\S]+?(?=(^## |\x00))/gm)) {
    txt = txt.replace(match[0], "");
  }
  // eslint-disable-next-line no-control-regex
  for (const match of txt.matchAll(/^## .*@private\b.*$[\s\S]+?(?=(^## |\x00))/gm)) {
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
    cache: { path: `${DIR_CACHE}/cflmd/api/content/${page.id}/child/attachment.json`, validSecs: { value: args.opts.cacheSecsPage, opt: "--cache-secs-page/CFLMD_CACHE_SECS_PAGE" } },
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
    // attachment._links.download: /download/attachments/{pageId}/{fileName}?version=1&modificationDate={epochMilliseconds}&api=v2
    //   {fileName} is URL-encoded
    const fsPath = `${DIR_CACHE}/cflmd${decodeURIComponent(attachment._links.download)}`;
    const fetchJSONOpts = {
      logFetch: logger.debug.bind(logger),
      cache: { path: fsPath, validSecs: { value: args.opts.cacheSecsImg, opt: "--cache-secs-img/CFLMD_CACHE_SECS_IMG" } },
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
        const json = libNode.jsonParsePathSync(f + ".json");
        if (sha1 === crypto.createHash("sha1").update(fs.readFileSync(f)).digest("hex")) {
          return json;
        }
      }
      logger.error(`uploading not implemented; will cause error`, { image, sha1 });
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
  txt = txt.replaceAll(/cfmd:(info|note|tip|warning)\b/g, "cflmd:$1"); // compatibility: <cfmd:info> <cfmd:note> <cfmd:tip> <cfmd:warning>

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
  txt = txt.replaceAll(/@cfmd:toc\b/g, "@cflmd:toc"); // compatibility
  for (const match of txt.matchAll(/^@cflmd:toc$/gm)) {
    txt = txt.replace(match[0], `<ac:structured-macro ac:name="toc" ac:schema-version="1" ac:macro-id="@cflmd:macro_id" />`);
  }
  return txt;
}

async function cflmdProcess2Pandoc0Ref(args: CflmdProcessArgs): Promise<string> {
  let txt = args.txts.at(-1)!.txt;
  // without maxBuffer or maxBuffer: 2**21 (2Mi): ENOBUFS; 2**26: 64Mi
  txt = child_process.execSync(`pandoc --from=markdown-auto_identifiers+autolink_bare_uris$(: -blank_before_blockquote)-citations+east_asian_line_breaks$(: -markdown_in_html_blocks)-smart+raw_attribute \
      --to=html --preserve-tabs --strip-comments $(: --no-highlight)`, { encoding: "utf8", maxBuffer: 2**26, input: txt });
  return txt;
}

async function cflmdProcess2Pandoc(args: CflmdProcessArgs): Promise<string> {
  let txt = args.txts.at(-1)!.txt;
  // -auto_identifiers  prevent: id="..." in <h2 id="タイトル---title">タイトル - TITLE</h2>
  // -auto_identifiers  prevent: id="..." in <h2 id="各os実装調査---linux">各OS実装調査 - Linux</h2>
  // -citations         prevent: @foo -> <span class="citation" data-cites="foo">@foo</span>
  // -smart             prevent: -- -> –
  // without maxBuffer or maxBuffer: 2**21 (2Mi): ENOBUFS; 2**26: 64Mi
  const json = JSON.parse(child_process.execSync(`pandoc --from=markdown-auto_identifiers+autolink_bare_uris$(: -blank_before_blockquote)-citations+east_asian_line_breaks$(: -markdown_in_html_blocks)-smart+raw_attribute \
      --to=json --preserve-tabs --strip-comments $(: --no-highlight)`, { encoding: "utf8", maxBuffer: 2**26, input: txt }));

  //    {"t": "Code", "c": [["", [], []], "\"quote_in_code\""]}
  // -> {"t": "Code", "c": [["", [], []], "@__cflmd:quot;quote_in_code@__cflmd:quot;"]},
  function convertCode(node: any): unknown {
    assert.deepEqual(node.t, "Code");
    assert.deepEqual(node.c.length, 2);
    assert.deepEqual(node.c[0].length, 3);
    assert.deepEqual(node.c[0][0], "");
    assert.deepEqual(node.c[0][1], []);
    assert.deepEqual(node.c[0][2], []);
    assert.ok(typeof node.c[1] === "string");
    return { t: "Code", c: [node.c[0], node.c[1].replaceAll(`"`, "@__cflmd:quot;")] };
  }

  const json2 = (() => {
    function convertCodeBlock(node: any): unknown {
      assert.deepEqual(node.t, "CodeBlock");
      assert.deepEqual(node.c.length, 2);
      assert.deepEqual(node.c[0].length, 3);
      assert.deepEqual(node.c[0][0], "");
      assert.ok(Array.isArray(node.c[0][1]) && (node.c[0][1].length === 0 || node.c[0][1].length === 1));
      assert.deepEqual(node.c[0][2], []);
      assert.ok(typeof node.c[1] === "string");
      const [[, classes], code] = node.c;
      const lang = classes[0] ?? "none";
      return { t: "Para", c: [{ t: "Str", c: `@__cflmd:codeBlock:${lang}:${Buffer.from(code).toString(("base64"))}` }] };
    }

    //    {"t": "Str", "c": "\"quote_in_p\""}
    // -> {"t": "Str", "c": "@__cflmd:quot;quote_in_p@__cflmd:quot;"}
    function convertStr(node: any): unknown {
      assert.deepEqual(node.t, "Str");
      assert.deepEqual(typeof node.c, "string");
      return { t: "Str", c: node.c.replaceAll(`"`, "@__cflmd:quot;") };
    }

    function transformNode(node: any): unknown {
      // () => isObject(): avoid type assertion by isObject(node)
      if ((() => isObject(node))()) {
        if (node.t === "Code") return convertCode(node as any);
        if (node.t === "CodeBlock") return convertCodeBlock(node as any);
        if (node.t === "Str") return convertStr(node as any);
        return Object.fromEntries(Object.entries(node).map(([k, v]) => [k, transformNode(v)]));
      }
      if (Array.isArray(node)) {
        return node.map(transformNode);
      }
      return node;
    }

    const json2 = transformNode(json);
    return json2;
  })();

  // without maxBuffer or maxBuffer: 2**21 (2Mi): ENOBUFS; 2**26: 64Mi
  txt = child_process.execSync(`pandoc --from=json --to=html`, { encoding: "utf8", maxBuffer: 2 ** 26, input: JSON.stringify(json2) });
  return txt;
}

async function cflmdProcess3HTMLPostProcess(args: CflmdProcessArgs): Promise<string> {
  let txt = args.txts.at(-1)!.txt;
  let match;

  // 0 HACK
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
  txt = cflmdProcess3HTMLPostProcessCode(txt);

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
    let re = /<a\s+href="(?<href>__cfl_top__\/(display|pages)\/[^"]+)">(\k<href>)<\/a>/;
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

  // quot ("): @__cflmd:quot; -> &quot;
  txt = txt.replaceAll(/@__cflmd:quot;/g, "&quot;");
  cflmdWrite(args.txts, "3.postp.quot.html", txt, true);

  // z @cflmd:macro_id -> @__cflmd:macro_id:0000
  txt = txt.replaceAll(/@cfmd:macro_id\b/g, "@cflmd:macro_id"); // compatibility: @cfmd:macro_id
  let macroID = 0;
  while ((match = txt.match(/@cflmd:macro_id\b/g)) !== null) {
    // txt = txt.replace(/@cflmd:macro_id\b/, `00000000-0000-0000-0000-${String(++macroID).padStart(12, "0")}`); // starts from 1: 00000000-0000-0000-0000-000000000001
    txt = txt.replace(/@cflmd:macro_id\b/, `@__cflmd:macro_id:${String(macroID++).padStart(4, "0")}`);
  }
  cflmdWrite(args.txts, "3.postp.z_macro_id.html", txt, true);

  return txt;
}

// ```lang
// @cflmd:collapse
// @cflmd:title:TITLE
// BODY
// ```
// ↓
// {"t": "Para", "c": [{"t": "Str", "c": "@__cflmd:codeBlock:lang:BASE64"}]}
// ↓
// structured-macro xml
function cflmdProcess3HTMLPostProcessCode(txt: string): string {
  // <p>@__cflmd:codeBlock:none:Y29kZV9ibG9ja19mZW5jZWQgISIjJCUmJygpKissLS4vOjs8PT4/QFtcXV5fYHt8fT0KY29kZV9ibG9ja19mZW5jZWQgbGluZSAy</p>
  let match;
  while ((match = txt.match(/<p>@__cflmd:codeBlock:(?<lang>[^:]+):(?<code>.*?)<\/p>/)) !== null) {
    assert.ok(match.groups !== undefined);

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
    }[match.groups.lang] ?? null;

    let code = Buffer.from(match.groups.code, "base64").toString("utf8");
    code = code.replaceAll(/@cfmd:collapse\b/g, "@cflmd:collapse"); // compatibility: @cfmd:collapse
    code = code.replaceAll(/@cfmd:title:/g, "@cflmd:title:"); // compatibility @cfmd:title
    let collapse = false;
    if (strFirstLine(code) === "@cflmd:collapse") {
      collapse = true;
      code = strRemoveFirstLine(code);
    }
    let title = null;
    if (strFirstLine(code).startsWith("@cflmd:title:")) {
      title = strFirstLine(code).substring("@cflmd:title:".length);
      code = strRemoveFirstLine(code);
    }

    // old; remove me
    // // pandoc: CDATA中に ">" が入っているとCDATAが空になる
    // // IE's conditional comment として解釈されている気がする https://github.com/kangax/html-minifier/issues/1161
    // const body2 = body.replaceAll(">", "__CFLMD_HACK_CDATA_GT__");

    const xml = `<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="@cflmd:macro_id">${cflLang === null ? "" : `<ac:parameter ac:name="language">${cflLang}</ac:parameter>`}${title === null ? "" : `<ac:parameter ac:name="title">${title}</ac:parameter>`}${collapse ? `<ac:parameter ac:name="collapse">true</ac:parameter>` : ""}
  <ac:plain-text-body><![CDATA[${strEscapeCdata(code)}
]]>
  </ac:plain-text-body>
</ac:structured-macro>`;
      txt = strReplaceAll(txt, match[0], xml);
  }
  return txt;
}

async function cflmdProcess4FormatHtml(args: CflmdProcessArgs): Promise<string> {
  let txt = args.txts.at(-1)!.txt;
  // without `cat |`: ENXIO -- I guess it's because fd 0 is unix socket (inspected by lsof)
  txt = child_process.execSync(`cat | c.js txt-confluence-html-format`, { encoding: "utf8", env: { ...process.env, NODE_OPTIONS: "--enable-source-maps" }, input: txt });
  return txt;
}

function cflmdMaybeWriteDiff(pathA: string, pathB: string, pathOut: string) {
  // without maxBuffer or maxBuffer: 2**21 (2Mi): ENOBUFS; 2**26: 64Mi
  const diff = child_process.execSync(`diff -u ${strEscapeShell(pathA)} ${strEscapeShell(pathB)} || true`, { encoding: "utf8", maxBuffer: 2 ** 26 });
  if (diff === "") {
    if (fs.existsSync(pathOut)) {
      fs.unlinkSync(pathOut);
    }
    return;
  }
  logger.debug(`${pathOut} : ${diff.split(/\r?\n/).length - 1} lines`);
  fs.writeFileSync(pathOut, diff);
}

function cflmdWrite0(name: string, txt: string) {
  fs.writeFileSync(`${DIR_CACHE}/cflmd/last/${name}`, txt);
}

function cflmdWrite(txts: { name: string; txt: string }[], name: string, txt: string, doDiff: boolean) {
  txts.push({ name, txt });
  fs.writeFileSync(`${DIR_CACHE}/cflmd/last/${name}`, txt);
  if (!doDiff) return;
  const pathA = `${DIR_CACHE}/cflmd/last/${txts.at(-2)!.name}`;
  const pathB = `${DIR_CACHE}/cflmd/last/${name}`;
  const pathOut = `${DIR_CACHE}/cflmd/last/${name}.diff`;
  cflmdMaybeWriteDiff(pathA, pathB, pathOut);
}

// -----------------------------------------------------------------------------
// EOF

// import whyIsNodeRunning from "why-is-node-running";
// whyIsNodeRunning();
