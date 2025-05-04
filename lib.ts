// SPDX-FileCopyrightText: Copyright (c) 2023-2025 Wataru Ashihara <wataash0607@gmail.com>
// SPDX-License-Identifier: Apache-2.0

import * as assert from "node:assert/strict";

/**
 * breakpoint
 */
export function bp(): void {
  return;
}

export function debugInWebStorm(): boolean {
  if (process.env.NODE_OPTIONS === undefined) return false;
  // --require /home/wsh/.local/share/JetBrains/Toolbox/apps/webstorm/plugins/javascript-debugger/debugConnector.js
  return process.env.NODE_OPTIONS.includes("webstorm");
}

export async function delayed<T>(ms: number, fn: () => Promise<T>): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, ms));
  return fn();
}

export async function fetchCheckJSON(url: Parameters<typeof fetch>[0], init: NonNullable<Parameters<typeof fetch>[1]>): Promise<[Awaited<ReturnType<typeof fetch>>, any]> {
  const [resp, respTxt] = await fetchCheckTxt(url, init);
  const json = JSON.parse(respTxt);
  return [resp, json];
}

export async function fetchCheckTxt(url: Parameters<typeof fetch>[0], init: NonNullable<Parameters<typeof fetch>[1]>): Promise<[Awaited<ReturnType<typeof fetch>>, string]> {
  const resp = await fetch(url, init);
  const respTxt = await resp.text();
  if (!resp.ok) {
    console.error(`${init.method} ${url}: ${resp.status} ${resp.statusText}`);
    console.warn(`respTxt: ${respTxt}`);
    throw new Error(`${init.method} ${url}: ${resp.status} ${resp.statusText}`);
  }
  return [resp, respTxt];
}

export class Fn {
  static debounce<T extends (...args: any[]) => any>(ms: number, fn: T): T {
    let timeoutID = 0;
    // @ts-expect-error
    return (...args) => {
      clearTimeout(timeoutID);
      // @ts-expect-error
      timeoutID = setTimeout(() => {
        fn(...args);
      }, ms);
    };
  }

  static throttle<T extends (...args: any[]) => any>(ms: number, fn: T): T {
    let timeoutId = 0;
    // @ts-expect-error
    return (...args) => {
      if (timeoutId !== 0) {
        return;
      }
      fn(...args);
      // @ts-expect-error
      timeoutId = setTimeout(() => {
        timeoutId = 0;
        fn(...args);
      }, ms);
    }
  }
}

export function html(opts: { body: string, head?: string, lang?: string, title?: string }): string {
  opts.head ??= "";
  opts.lang ??= "ja-JP"; // en
  opts.title ??= "TITLE";

  return `<!DOCTYPE html>
<html lang="${opts.lang}">
<head>
  <meta charset="utf-8" />
  <title>${opts.title}</title>
  ${opts.head}
</head>

<body>
  ${opts.body}
</body>
</html>
`;
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isScalar(j: JsonValue): j is JsonPrimitive {
  return (typeof j === "string" || typeof j === "number" || j === false || j === true || j === null);
}

// https://github.com/sindresorhus/type-fest/blob/main/source/basic.d.ts
export type JsonObject = {[Key in string]: JsonValue} & {[Key in string]?: JsonValue | undefined};
export type JsonArray = JsonValue[] | readonly JsonValue[];
export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonArray;

export function isJSONObject(value: JsonValue): value is JsonObject {
  // https://github.com/jonschlinkert/isobject/blob/master/index.js
  return value !== null && typeof value === "object" && Array.isArray(value) === false;
}

export function jsonFlat(j: JsonValue, _key = ""): JsonValue {
  if (typeof j === "string" || typeof j === "number" || j === false || j === true || j === null) {
    return j;
  }
  if (Array.isArray(j)) {
    if (j.length === 0) {
      return [];
    }
    const ret: { [key: string]: JsonValue } = {};
    for (const [i, value] of j.entries()) {
      if (typeof value === "string" || typeof value === "number" || value === false || value === true || value === null) {
        ret[`${_key}[${i}]`] = value;
        continue;
      }
      if (Array.isArray(value) && value.length === 0) {
        ret[`${_key}[${i}]`] = [];
        continue;
      }
      const flatObj = jsonFlat(value, `${_key}[${i}]`);
      // @ts-expect-error
      for (const [k, v] of Object.entries(flatObj)) {
        ret[k] = v;
      }
    }
    return ret;
  }
  assert.ok(j !== undefined && j.constructor === Object);
  const ret = {};
  for (const [k, v] of Object.entries(j)) {
    if (typeof v === "string" || typeof v === "number" || v === false || v === true || v === null) {
      // @ts-expect-error
      ret[_key === "" ? `${k}` : `${_key}.${k}`] = v;
      continue;
    }
    if (Array.isArray(v) && v.length === 0) {
      // @ts-expect-error
      ret[_key === "" ? `${k}` : `${_key}.${k}`] = [];
      continue;
    }
    const flatObj = jsonFlat(v, _key === "" ? `${k}` : `${_key}.${k}`);
    // @ts-expect-error
    for (const [k2, v2] of Object.entries(flatObj)) {
      // @ts-expect-error
      ret[k2] = v2;
    }
  }
  return ret;
}

if (0) {
  assert.deepEqual(jsonFlat(null), null);
  assert.deepEqual(jsonFlat([null]), {"[0]": null});
  assert.deepEqual(jsonFlat([]), []);
  assert.deepEqual(jsonFlat({
    "j": { "a": "b", "c": ["d", ["p"], []], "e": [] },
    "k": [1, true, [null]],
    "l": null
   }), {
    "j.a": "b",
    "j.c[0]": "d",
    "j.c[1][0]": "p",
    "j.c[2]": [],
    "j.e": [],
    "k[0]": 1,
    "k[1]": true,
    "k[2][0]": null,
    "l": null,
  });
}

export function jsonFlatArray(j: JsonValue, opts: { width: number }, key = ""): string[] {
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
    return [...j.entries()].map(([i, value]) => jsonFlatArray(value, opts, `${key}[${i}]`)).flat();
  }
  assert.ok(j !== undefined && j.constructor === Object);
  if (Object.keys(j).length === 0) {
    return key === "" ? ["{}"] : [`${key}: {}`];
  }
  // return Object.entries(j).map(([key, value]) => `.${key}: ${jsonFlatArray(value, {width: opts.width - key.length - 3 /* .:SPACE */})}`);
  return Object.entries(j).map(([thisKey, value]) => jsonFlatArray(value, opts, `${key}.${thisKey}`)).flat();
}

if (0) {
  const json = {
    "j": { "a": "b", "c": "d", "e": "f" },
    "k": [1, true, null]
  };
  assert.deepEqual(`${jsonFlatArray(json, { width: 1 }).join("\n")}\n`, `\
.j.a: "b"
.j.c: "d"
.j.e: "f"
.k[0]: 1
.k[1]: true
.k[2]: null
`);
  assert.deepEqual(`${jsonFlatArray(json, { width: 16 }).join("\n")}\n`, `\
.j.a: "b"
.j.c: "d"
.j.e: "f"
.k[0]: 1
.k[1]: true
.k[2]: null
`);
  assert.deepEqual(`${jsonFlatArray(json, { width: 17 }).join("\n")}\n`, `\
.j.a: "b"
.j.c: "d"
.j.e: "f"
.k: [1,true,null]
`);
  assert.deepEqual(`${jsonFlatArray(json, { width: 28 }).join("\n")}\n`, `\
.j.a: "b"
.j.c: "d"
.j.e: "f"
.k: [1,true,null]
`);
  assert.deepEqual(`${jsonFlatArray(json, { width: 29 }).join("\n")}\n`, `\
.j: {"a":"b","c":"d","e":"f"}
.k: [1,true,null]
`);
  assert.deepEqual(`${jsonFlatArray(json, { width: 48 }).join("\n")}\n`, `\
.j: {"a":"b","c":"d","e":"f"}
.k: [1,true,null]
`);
  assert.deepEqual(`${jsonFlatArray(json, { width: 49 }).join("\n")}\n`, `\
{"j":{"a":"b","c":"d","e":"f"},"k":[1,true,null]}
`);

  assert.deepEqual(jsonFlatArray([42, json, null], { width: 1 }), [
    '[0]: 42',
    '[1].j.a: "b"',
    '[1].j.c: "d"',
    '[1].j.e: "f"',
    '[1].k[0]: 1',
    '[1].k[1]: true',
    '[1].k[2]: null',
    '[2]: null'
  ]);
}

export function jsonShrinkKey(json: JsonValue): JsonValue {
  if (typeof json === "string" || typeof json === "number" || json === false || json === true || json === null) {
    return json;
  }
  if (Array.isArray(json)) {
    return json.map(jsonShrinkKey);
  }
  if (json.constructor !== Object) {
    throw new Error(`passed a non-JSON object: ${JSON.stringify(json)}`);
  }
  const jsonShrinked = {};
  for (const [k, v] of Object.entries(json)) {
    if (typeof v === "string" || typeof v === "number" || v === false || v === true || v === null) {
      // @ts-expect-error
      jsonShrinked[k] = v;
      continue;
    }
    if (Array.isArray(v)) {
      const vShrinked = jsonShrinkKey(v);
      // @ts-expect-error
      jsonShrinked[k] = vShrinked;
      continue;
    }
    const vShrinked = jsonShrinkKey(v);
    assert.strictEqual(v.constructor, Object);
    // @ts-expect-error
    assert.strictEqual(vShrinked.constructor, Object);
    // @ts-expect-error
    for (const [subK, subV] of Object.entries(vShrinked)) {
      // @ts-expect-error
      jsonShrinked[`${k}.${subK}`] = subV;
    }
  }
  return jsonShrinked;
}

if (0) {
  assert.deepEqual(jsonShrinkKey({ "a": { "b": { "c": "d" } } , "e": [{ "f": { "g": null } }] }),
                                 { "a.b.c": "d",                "e": [{ "f.g": null }] });
  assert.deepEqual(jsonShrinkKey([null]), [null]);
  assert.deepEqual(jsonShrinkKey(42), 42);
}

/**
 * line number
 */
export function line(): number {
  let callSites: NodeJS.CallSite[];
  // https://v8.dev/docs/stack-trace-api
  const tmp = Error.prepareStackTrace;
  Error.prepareStackTrace = (err, stackTraces) => stackTraces;
  // @ts-expect-error
  callSites = new Error().stack;
  Error.prepareStackTrace = tmp;
  // @ts-expect-error
  return callSites[1].getLineNumber();
}

export class MyError extends Error {
  toJSON() {
    return { message: this.message, stack: this.stack };
  }
}

declare global {
  interface Object {
    keys(): string[];
    _keys(): string[]; // in case of obj.keys (obj["keys"]) is defined
    __keys(): string[]; // the last resort

    // /home/wsh/qjs/tesjs/node_modules/typescript/lib/lib.es2017.object.d.ts
    // interface ObjectConstructor {
    // values<T>(o: { [s: string]: T; } | ArrayLike<T>): T[];
    // values(o: {}): any[];
    values<T>(this: { [s: string]: T; }): T[];
    _values<T>(this: { [s: string]: T; }): T[];
    __values<T>(this: { [s: string]: T; }): T[];
    // values(this: {}): any[]; // ({}).values()... 意味ない？ ↑ と順序入れ替えると効果あるようだ; これ以上調べるならTypeScript debugする

    // entries<T>(o: { [s: string]: T; } | ArrayLike<T>): [string, T][];
    // entries(o: {}): [string, any][];
    entries<T>(this: { [s: string]: T; }): [string, T][];
    _entries<T>(this: { [s: string]: T; }): [string, T][];
    __entries<T>(this: { [s: string]: T; }): [string, T][];
    // entries(this: {}): [string, any][];

    sort<T>(this: T, compareFn?: (a: keyof T, b: keyof T) => number): T; // : sorted<T>
    _sort<T>(this: T, compareFn?: (a: keyof T, b: keyof T) => number): T; // : sorted<T>
    __sort<T>(this: T, compareFn?: (a: keyof T, b: keyof T) => number): T; // : sorted<T>
  }
}
// 2025-05-03 playwright がバグる
// Object.prototype.keys = Object.prototype._keys = Object.prototype.__keys = function() { return Object.keys(this); };
// Object.prototype.values = Object.prototype._values = Object.prototype.__values = function() { return Object.values(this); };
// Object.prototype.entries = Object.prototype._entries = Object.prototype.__entries = function() { return Object.entries(this); };
// Object.prototype.sort = Object.prototype._sort = Object.prototype.__sort = function(compareFn) {
//   // @ts-expect-error
//   for (const key of Object.keys(this).sort(compareFn)) {
//     // @ts-expect-error
//     const val = this[key];
//     // @ts-expect-error
//     delete this[key];
//     // @ts-expect-error
//     this[key] = val;
//   }
//   return this;
// }

// TODO: type puzzle
// : Omit<T, keys[number]> // error
export function objExceptKeys<T extends {}>(obj: T, keys: Array<keyof T>): T {
  // @ts-expect-error
  return Object.keys(obj).filter((key) => !keys.includes(key)).reduce((acc, key) => (acc[key] = obj[key], acc), {});
}

if (0) {
  // @ts-expect-error
  objExceptKeys({ a: 1, b: 2, c: 3 }, ["a", "z"]);
  assert.deepEqual(objExceptKeys({ a: 1, b: 2, c: 3 }, ["a"]), { b: 2, c: 3 });
  assert.deepEqual(objExceptKeys({ a: 1, b: 2, c: 3 }, ["a", "b"]), { c: 3 });
}

export function objectHistograms(objs: object[]): { [key: string]: { [key: string]: number } } {
  if (!Array.isArray(objs)) throw new Error(`objs is not array: ${JSON.stringify(objs)}`);
  for (const [i, obj] of objs.entries()) {
    if (obj !== null && typeof obj === "object" && obj.constructor === Object) continue;
    throw new Error(`objs[${i}] is not object: ${JSON.stringify(obj)}`);
  }
  const ret = {};
  for (const obj of objs) {
    for (const key of Object.keys(obj)) {
      // @ts-expect-error
      ret[key] ??= {};
      // @ts-expect-error
      ret[key][obj[key]] ??= 0;
      // @ts-expect-error
      ret[key][obj[key]]++;
    }
  }
  return ret;
}

export function objectHistogramsPretty(objs: object[], max = 100): { [key: string]: { [key: string]: number } } {
  const ret = objectHistograms(objs);
  for (const [k, hist] of Object.entries(ret)) {
    let histSortedByCount = Object.entries(hist).sort((a, b) => b[1] - a[1]);
    histSortedByCount = histSortedByCount.slice(0, max);
    ret[k] = Object.fromEntries(histSortedByCount); // Object.fromEntries() -> now not sorted
  }
  return ret;
}

export function objectHistogramsMap<T>(objs: { [key: string]: T }[]): { [key: string]: Map<T, number> } {
  if (!Array.isArray(objs)) throw new Error(`objs is not array: ${JSON.stringify(objs)}`);
  for (const [i, obj] of objs.entries()) {
    if (obj !== null && typeof obj === "object" && obj.constructor === Object) continue;
    throw new Error(`objs[${i}] is not object: ${JSON.stringify(obj)}`);
  }
  const ret = {};
  for (const obj of objs) {
    for (const key of Object.keys(obj)) {
      // @ts-expect-error
      ret[key] ??= new Map();
      // @ts-expect-error
      ret[key].set(obj[key], ret[key].get(obj[key]) ?? 0 + 1);
    }
  }
  return ret;
}

export function objectHistogramsMapPretty(maps: Map<any, any>[], max = 100): { [key: string]: number } {
  // @ts-expect-error
  const ret = objectHistogramsMap(maps);
  for (const [k, hist] of Object.entries(ret)) {
    let histSortedByCount = [...hist].sort((a, b) => b[1] - a[1]);
    histSortedByCount = histSortedByCount.slice(0, max);
    ret[k] = new Map(histSortedByCount); // new Map() -> still sorted? (not tested)
  }
  // @ts-expect-error
  return ret;
}

if (0) {
  // @ts-expect-error
  assert.throws(() => objectHistograms(null), { message: 'objs is not array: null' });
  assert.throws(() => objectHistograms([{}, new Date()]), { message: /^objs\[1] is not object: ....-..-..T..:..:......Z$/ });

  const objs = [
    { key1: 1, key2: 2, keyArr: ["val1", "val2"], keyObj: { a: 42 } },
    { key1: "1", key2: 5, keyArr: ["val1", "val2"], keyObj: { b: 43 } },
    { key1: null, key2: "5" },
  ];
  const maps = objs.map((obj) => new Map(Object.entries(obj)));
  // const maps = [
  //   new Map(Object.entries({ key1: 1, key2: 2, keyArr: ["val1", "val2"], keyObj: { a: 42 } })),
  //   new Map([["key1", "1"], ["key2", 5], ["keyArr", ["val1", "val2"]], ["keyObj", { b: 43 }]])

  assert.deepEqual(objectHistograms(objs),          { key1: { '1': 2, null: 1 }, key2: { '2': 1, '5': 2 }, keyArr: { 'val1,val2': 2 }, keyObj: { '[object Object]': 2 } });
  assert.deepEqual(objectHistogramsPretty(objs, 1), { key1: { '1': 2 },          key2: { '5': 2 },         keyArr: { 'val1,val2': 2 }, keyObj: { '[object Object]': 2 } });
  assert.deepEqual(objectHistogramsPretty(objs, 2), { key1: { '1': 2, null: 1 }, key2: { '2': 1, '5': 2 }, keyArr: { 'val1,val2': 2 }, keyObj: { '[object Object]': 2 } });

  // @ts-expect-error
  assert.throws(() => objectHistogramsMap(null), { message: 'objs is not array: null' });
  // @ts-expect-error
  assert.throws(() => objectHistogramsMap([{}, new Date()]), { message: /^objs\[1] is not object: ....-..-..T..:..:......Z$/ });

  // TODO: ['val1', 'val2'] => 2
  // @ts-expect-error
  assert.deepEqual(objectHistogramsMap(objs),          { key1: new Map([[1, 1], ['1', 1], [null, 1]]), key2: new Map([[2, 1], [5, 1], ["5", 1]]), keyArr: new Map([[['val1', 'val2'], 1], [['val1', 'val2'], 1]]), keyObj: new Map([[{ a: 42 }, 1], [{ b: 43 }, 1]]) });
  // @ts-expect-error
  assert.deepEqual(objectHistogramsMapPretty(objs, 1), { key1: new Map([[1, 1]                     ]), key2: new Map([[2, 1]                  ]), keyArr: new Map([[['val1', 'val2'], 1]                       ]), keyObj: new Map([[{ a: 42 }, 1]                ]) });
  // @ts-expect-error
  assert.deepEqual(objectHistogramsMapPretty(objs, 2), { key1: new Map([[1, 1], ['1', 1]           ]), key2: new Map([[2, 1], [5, 1],         ]), keyArr: new Map([[['val1', 'val2'], 1], [['val1', 'val2'], 1]]), keyObj: new Map([[{ a: 42 }, 1], [{ b: 43 }, 1]]) });
}

/**
 * @param keys obj must have all keys
 */
export function objectOnlyKey(obj: object, keys: string[], keyOrder: "obj" | "keys" = "obj"): Partial<typeof obj> {
  for (const k of keys) {
    assert.ok(k in obj);
  }
  if (keyOrder === "obj") {
    return Object.keys(obj).reduce((acc, k) => {
      // @ts-expect-error
      if (keys.includes(k)) acc[k] = obj[k];
      return acc;
    }, {});
  } else {
    return keys.reduce((acc, k) => {
      // @ts-expect-error
      acc[k] = obj[k];
      return acc;
    }, {});
  }
}

export function mapOnlyKey(map: Map<any, any>, keys: string[]): Partial<typeof map> {
  return [...map.keys()].reduce((acc, k) => {
    if (keys.includes(k)) acc.set(k, map.get(k));
    return acc;
  }, new Map());
}

export function objSort<T extends {}>(obj: T, compareFn?: (a: keyof T, b: keyof T) => number): T { // : sorted<T>
  // @ts-expect-error
  return Object.keys(obj).sort(compareFn).reduce((acc, key) => (acc[key] = obj[key], acc), {});
}

if (0) {
  const t477 = objSort({ b: 2, a: 1 }, (a, b) => a.localeCompare(b));
  const t482 = ({ b: 2, a: 1 }).sort((a, b) => a.localeCompare(b));
}

export function objectToMap<T>(obj: { [key: string]: T }): Map<string, T> {
  return new Map(Object.entries(obj));
}

export function mapToObject<T>(map: Map<any, T>): { [key: string]: T } {
  return Object.fromEntries(map);
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

export class Str {
  /**
   * https://stackoverflow.com/questions/1779858/how-do-i-escape-a-string-for-a-shell-command-in-node
   */
  static escapeShell(str: string): string {
    return `"${str.replace(/(["'$`\\])/g, "\\$1")}"`;
  }
}

export function strJSONFlat(j: unknown, opts: { width: number }, key?: string): string[] {
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
    return [...j.entries()].map(([i, value]) => strJSONFlat(value, opts, `${key}[${i}]`)).flat();
  }
  assert.ok(j !== undefined && j.constructor === Object);
  if (Object.keys(j).length === 0) {
    return key === "" ? ["{}"] : [`${key}: {}`];
  }
  // return Object.entries(j).map(([key, value]) => `.${key}: ${strJSONFlat(value, {width: opts.width - key.length - 3 /* .:SPACE */})}`);
  return Object.entries(j).map(([thisKey, value]) => strJSONFlat(value, opts, `${key}.${thisKey}`)).flat();
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

export function reExecThrow(regexp: RegExp, string: string): RegExpExecArray {
  const reArr = reExec(regexp, string);
  if (Array.isArray(reArr)) return reArr;
  throw new Error(reArr);
}

/**
 * https://ja.javascript.info/task/shuffle
 */
export function shuffle<T>(array: T[]): T[] {
  for (let i = array.length - 1; i > 0; i--) {
    let j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

export function strEscapeShell(str: string): string {
  return Str.escapeShell(str);;
}

/**
 * Visualize control characters
 */
export function strCon(s: string): string {
  // https://en.wikipedia.org/wiki/ASCII
  // Binary	Oct	Dec	Hex	Abbreviation	Unicode Control Pictures[b]	Caret notation[c]	C escape sequence[d]	Name (1967)
  // 1963	1965	1967
  return s
    .replaceAll("\x00", "␀") // __mark__ 000 0000	000	0	00	NULL	NUL	␀	^@	\0 [e]	Null
    .replaceAll("\x01", "␁") // __mark__ 000 0001	001	1	01	SOM	SOH	␁	^A		Start of Heading
    .replaceAll("\x02", "␂") // __mark__ 000 0010	002	2	02	EOA	STX	␂	^B		Start of Text
    .replaceAll("\x03", "␃") // __mark__ 000 0011	003	3	03	EOM	ETX	␃	^C		End of Text
    .replaceAll("\x04", "␄") // __mark__ 000 0100	004	4	04	EOT	␄	^D		End of Transmission
    .replaceAll("\x05", "␅") // __mark__ 000 0101	005	5	05	WRU	ENQ	␅	^E		Enquiry
    .replaceAll("\x06", "␆") // __mark__ 000 0110	006	6	06	RU	ACK	␆	^F		Acknowledgement
    .replaceAll("\x07", "␇") // __mark__ 000 0111	007	7	07	BELL	BEL	␇	^G	\a	Bell
    .replaceAll("\x08", "␈") // __mark__ 000 1000	010	8	08	FE0	BS	␈	^H	\b	Backspace[f][g]
    .replaceAll("\x09", "␉") // __mark__ 000 1001	011	9	09	HT/SK	HT	␉	^I	\t	Horizontal Tab[h]
    // .replaceAll("\x0a", "␊") // __mark__ 000 1010	012	10	0A	LF	␊	^J	\n	Line Feed
    .replaceAll("\x0b", "␋") // __mark__ 000 1011	013	11	0B	VTAB	VT	␋	^K	\v	Vertical Tab
    .replaceAll("\x0c", "␌") // __mark__ 000 1100	014	12	0C	FF	␌	^L	\f	Form Feed
    .replaceAll("\x0d", "␍") // __mark__ 000 1101	015	13	0D	CR	␍	^M	\r	Carriage Return[i]
    .replaceAll("\x0e", "␎") // __mark__ 000 1110	016	14	0E	SO	␎	^N		Shift Out
    .replaceAll("\x0f", "␏") // __mark__ 000 1111	017	15	0F	SI	␏	^O		Shift In
    .replaceAll("\x10", "␐") // __mark__ 001 0000	020	16	10	DC0	DLE	␐	^P		Data Link Escape
    .replaceAll("\x11", "␑") // __mark__ 001 0001	021	17	11	DC1	␑	^Q		Device Control 1 (often XON)
    .replaceAll("\x12", "␒") // __mark__ 001 0010	022	18	12	DC2	␒	^R		Device Control 2
    .replaceAll("\x13", "␓") // __mark__ 001 0011	023	19	13	DC3	␓	^S		Device Control 3 (often XOFF)
    .replaceAll("\x14", "␔") // __mark__ 001 0100	024	20	14	DC4	␔	^T		Device Control 4
    .replaceAll("\x15", "␕") // __mark__ 001 0101	025	21	15	ERR	NAK	␕	^U		Negative Acknowledgement
    .replaceAll("\x16", "␖") // __mark__ 001 0110	026	22	16	SYNC	SYN	␖	^V		Synchronous Idle
    .replaceAll("\x17", "␗") // __mark__ 001 0111	027	23	17	LEM	ETB	␗	^W		End of Transmission Block
    .replaceAll("\x18", "␘") // __mark__ 001 1000	030	24	18	S0	CAN	␘	^X		Cancel
    .replaceAll("\x19", "␙") // __mark__ 001 1001	031	25	19	S1	EM	␙	^Y		End of Medium
    .replaceAll("\x1a", "␚") // __mark__ 001 1010	032	26	1A	S2	SS	SUB	␚	^Z		Substitute
    .replaceAll("\x1b", "␛") // __mark__ 001 1011	033	27	1B	S3	ESC	␛	^[	\e[j]	Escape[k]
    .replaceAll("\x1c", "␜") // __mark__ 001 1100	034	28	1C	S4	FS	␜	^\		File Separator
    .replaceAll("\x1d", "␝") // __mark__ 001 1101	035	29	1D	S5	GS	␝	^]		Group Separator
    .replaceAll("\x1e", "␞") // __mark__ 001 1110	036	30	1E	S6	RS	␞	^^[l]		Record Separator
    .replaceAll("\x1f", "␟") // __mark__ 001 1111	037	31	1F	S7	US	␟	^_		Unit Separator
    .replaceAll("\x7f", "␡") // __mark__ 111 1111	177	127	7F	DEL	␡	^?		Delete[m][g]
    ;
}

export function strConNL(s: string): string {
  return strCon(s).replaceAll("\n", "␊");
}

export function strSnip(s: string, len: number): string {
  s = s.replaceAll("\n", "⏎");
  if (s.length <= len) return s;
  len = Math.floor(len / 2);
  return `${s.slice(0, len)} ... ${s.slice(s.length - len)}`;
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
// EOF
