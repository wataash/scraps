#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r"""
python mozc_dict.py dicts
python mozc_dict.py list
python mozc_dict.py add よみ 単語 --pos 名詞 --comment "コメント"
python mozc_dict.py add ふぁぶる Fable --pos 固有名詞 --reload
python mozc_dict.py import words.tsv --reload  # TSV: よみ<TAB>単語<TAB>品詞<TAB>コメント
python mozc_dict.py remove ふぁぶる
python mozc_dict.py reload
"""[1:]

import argparse
import dataclasses
import fcntl
import logging
import os
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from _colorize import get_colors  # Python 3.13+ (private API)
except ImportError:
    class _NoColors:
        RED = YELLOW = BLUE = WHITE = RESET = ""

    def get_colors(colorize=False, *, file=None):  # type: ignore[misc]
        return _NoColors


class MyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        c = get_colors(file=sys.stderr)
        color = {
            logging.CRITICAL: c.RED,
            logging.ERROR: c.RED,
            logging.WARNING: c.YELLOW,
            logging.INFO: c.BLUE,
            logging.DEBUG: c.WHITE,
        }[record.levelno]
        fn = "" if record.funcName == "<module>" else f" {record.funcName}()"
        fmt = f"{color}[%(levelname)1.1s %(asctime)s %(filename)s:%(lineno)d{fn}] %(message)s{c.RESET}"
        return logging.Formatter(fmt=fmt, datefmt="%T").format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(MyFormatter())
logger.addHandler(logger_handler)


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


DEFAULT_DB = Path("~/.config/mozc/user_dictionary.db").expanduser()

# mozc/src/protocol/user_dictionary_storage.proto: UserDictionary.PosType
POS_TABLE: list[tuple[int, str, str]] = [
    (0, "NO_POS", "品詞なし"),
    (1, "NOUN", "名詞"),
    (2, "ABBREVIATION", "短縮よみ"),
    (3, "SUGGESTION_ONLY", "サジェストのみ"),
    (4, "PROPER_NOUN", "固有名詞"),
    (5, "PERSONAL_NAME", "人名"),
    (6, "FAMILY_NAME", "姓"),
    (7, "FIRST_NAME", "名"),
    (8, "ORGANIZATION_NAME", "組織"),
    (9, "PLACE_NAME", "地名"),
    (10, "SA_IRREGULAR_CONJUGATION_NOUN", "名詞サ変"),
    (11, "ADJECTIVE_VERBAL_NOUN", "名詞形動"),
    (12, "NUMBER", "数"),
    (13, "ALPHABET", "アルファベット"),
    (14, "SYMBOL", "記号"),
    (15, "EMOTICON", "顔文字"),
    (16, "ADVERB", "副詞"),
    (17, "PRENOUN_ADJECTIVAL", "連体詞"),
    (18, "CONJUNCTION", "接続詞"),
    (19, "INTERJECTION", "感動詞"),
    (20, "PREFIX", "接頭語"),
    (21, "COUNTER_SUFFIX", "助数詞"),
    (22, "GENERIC_SUFFIX", "接尾一般"),
    (23, "PERSON_NAME_SUFFIX", "接尾人名"),
    (24, "PLACE_NAME_SUFFIX", "接尾地名"),
    (25, "WA_GROUP1_VERB", "動詞ワ行五段"),
    (26, "KA_GROUP1_VERB", "動詞カ行五段"),
    (27, "SA_GROUP1_VERB", "動詞サ行五段"),
    (28, "TA_GROUP1_VERB", "動詞タ行五段"),
    (29, "NA_GROUP1_VERB", "動詞ナ行五段"),
    (30, "MA_GROUP1_VERB", "動詞マ行五段"),
    (31, "RA_GROUP1_VERB", "動詞ラ行五段"),
    (32, "GA_GROUP1_VERB", "動詞ガ行五段"),
    (33, "BA_GROUP1_VERB", "動詞バ行五段"),
    (34, "HA_GROUP1_VERB", "動詞ハ行四段"),
    (35, "GROUP2_VERB", "動詞一段"),
    (36, "KURU_GROUP3_VERB", "動詞カ変"),
    (37, "SURU_GROUP3_VERB", "動詞サ変"),
    (38, "ZURU_GROUP3_VERB", "動詞ザ変"),
    (39, "RU_GROUP3_VERB", "動詞ラ変"),
    (40, "ADJECTIVE", "形容詞"),
    (41, "SENTENCE_ENDING_PARTICLE", "終助詞"),
    (42, "PUNCTUATION", "句読点"),
    (43, "FREE_STANDING_WORD", "独立語"),
    (44, "SUPPRESSION_WORD", "抑制単語"),
]
POS_NUM_BY_NAME = {name: num for num, en, ja in POS_TABLE for name in (en, ja)}
POS_JA_BY_NUM = {num: ja for num, _en, ja in POS_TABLE}


def pos_from_str(s: str) -> int:
    s = s.split(":")[0]  # Gboard TSV encodes locale as "名詞:ja"
    if s == "":
        return 1  # NOUN
    if s not in POS_NUM_BY_NAME:
        raise SystemExit(f"unknown POS: {s!r}; valid: {' '.join(ja for _, _, ja in POS_TABLE)}")
    return POS_NUM_BY_NAME[s]


# -----------------------------------------------------------------------------
# minimal protobuf (proto2) wire format codec

def _write_uvarint(n: int) -> bytes:
    """
    >>> _write_uvarint(1).hex()
    '01'
    >>> _write_uvarint(300).hex()
    'ac02'
    """
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _read_uvarint(data: bytes, i: int) -> tuple[int, int]:
    """
    >>> _read_uvarint(bytes.fromhex('ac02'), 0)
    (300, 2)
    """
    n = shift = 0
    while True:
        b = data[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, i
        shift += 7


def _varint_field(field: int, n: int) -> bytes:
    return _write_uvarint(field << 3 | 0) + _write_uvarint(n)


def _len_field(field: int, data: bytes) -> bytes:
    return _write_uvarint(field << 3 | 2) + _write_uvarint(len(data)) + data


def _iter_fields(data: bytes):
    """Yield (field_number, wire_type, value, raw_bytes) for each field."""
    i = 0
    while i < len(data):
        start = i
        tag, i = _read_uvarint(data, i)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            value, i = _read_uvarint(data, i)
        elif wire == 1:
            value, i = data[i:i + 8], i + 8
        elif wire == 2:
            ln, i2 = _read_uvarint(data, i)
            value, i = data[i2:i2 + ln], i2 + ln
        elif wire == 5:
            value, i = data[i:i + 4], i + 4
        else:
            raise ValueError(f"unsupported wire type {wire} at offset {start}")
        yield field, wire, value, data[start:i]


# -----------------------------------------------------------------------------
# mozc/src/protocol/user_dictionary_storage.proto

@dataclasses.dataclass
class Entry:
    key: str = ""
    value: str = ""
    comment: str | None = None
    pos: int | None = None  # None = absent (mozc treats as NOUN)
    locale: str | None = None
    unknown: list[bytes] = dataclasses.field(default_factory=list)

    @classmethod
    def parse(cls, data: bytes) -> "Entry":
        e = cls()
        for field, _wire, value, raw in _iter_fields(data):
            if field == 1:
                e.key = value.decode()
            elif field == 2:
                e.value = value.decode()
            elif field == 4:
                e.comment = value.decode()
            elif field == 5:
                e.pos = value
            elif field == 12:
                e.locale = value.decode()
            else:
                e.unknown.append(raw)
        return e

    def serialize(self) -> bytes:
        out = _len_field(1, self.key.encode()) + _len_field(2, self.value.encode())
        if self.comment is not None:
            out += _len_field(4, self.comment.encode())
        if self.pos is not None:
            out += _varint_field(5, self.pos)
        if self.locale is not None:
            out += _len_field(12, self.locale.encode())
        return out + b"".join(self.unknown)

    def pos_ja(self) -> str:
        return POS_JA_BY_NUM.get(self.pos if self.pos is not None else 1, f"?{self.pos}")


@dataclasses.dataclass
class Dictionary:
    id: int = 0
    name: str = ""
    entries: list[Entry] = dataclasses.field(default_factory=list)
    unknown: list[bytes] = dataclasses.field(default_factory=list)

    @classmethod
    def parse(cls, data: bytes) -> "Dictionary":
        d = cls()
        for field, _wire, value, raw in _iter_fields(data):
            if field == 1:
                d.id = value
            elif field == 3:
                d.name = value.decode()
            elif field == 4:
                d.entries.append(Entry.parse(value))
            else:
                d.unknown.append(raw)
        return d

    def serialize(self) -> bytes:
        out = _varint_field(1, self.id) + _len_field(3, self.name.encode())
        out += b"".join(_len_field(4, e.serialize()) for e in self.entries)
        return out + b"".join(self.unknown)


@dataclasses.dataclass
class Storage:
    version: int | None = None
    dictionaries: list[Dictionary] = dataclasses.field(default_factory=list)
    unknown: list[bytes] = dataclasses.field(default_factory=list)

    @classmethod
    def parse(cls, data: bytes) -> "Storage":
        s = cls()
        for field, _wire, value, raw in _iter_fields(data):
            if field == 1:
                s.version = value
            elif field == 2:
                s.dictionaries.append(Dictionary.parse(value))
            else:
                s.unknown.append(raw)
        return s

    def serialize(self) -> bytes:
        out = b"" if self.version is None else _varint_field(1, self.version)
        out += b"".join(_len_field(2, d.serialize()) for d in self.dictionaries)
        return out + b"".join(self.unknown)


def test_roundtrip():
    # bytes as written by mozc_tool's dictionary_tool (empty "User Dictionary 1")
    orig = bytes.fromhex("122808abe995d6c1fda78ce0011a11557365722044696374696f6e61727920312208 0a00 1200 2200 2801".replace(" ", ""))
    s = Storage.parse(orig)
    assert s.dictionaries[0].name == "User Dictionary 1"
    assert s.serialize() == orig


# -----------------------------------------------------------------------------

def load_storage(db: Path) -> Storage:
    if not db.exists():
        logger.info(f"{db} does not exist; starting with empty storage")
        return Storage()
    return Storage.parse(db.read_bytes())


def save_storage(db: Path, storage: Storage) -> None:
    # same lock file as mozc's ProcessMutex (base/process_mutex.cc): flock on .<basename>.lock
    lock_path = db.parent / f".{db.name}.lock"
    db.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_fp:
        try:
            fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(f"{lock_path} is locked; close the mozc dictionary tool and retry")
        if db.exists():
            backup = Path(f"{db}.bak")
            shutil.copy2(db, backup)
            logger.info(f"backup: {backup}")
        fd, tmp = tempfile.mkstemp(dir=db.parent, prefix=f".{db.name}.tmp")
        try:
            with os.fdopen(fd, "wb") as fp:
                fp.write(storage.serialize())
                fp.flush()
                os.fsync(fp.fileno())
            os.chmod(tmp, 0o644)
            os.replace(tmp, db)
        except BaseException:
            os.unlink(tmp)
            raise
        fcntl.flock(lock_fp, fcntl.LOCK_UN)
    logger.info(f"wrote {db}")


def find_dictionary(storage: Storage, name: str | None, create: bool) -> Dictionary:
    if name is None:
        if storage.dictionaries:
            return storage.dictionaries[0]
        name = "User Dictionary 1"  # same default name as mozc_tool
    for d in storage.dictionaries:
        if d.name == name:
            return d
    if not create:
        raise SystemExit(f"dictionary {name!r} not found; existing: {[d.name for d in storage.dictionaries]}")
    ids = {d.id for d in storage.dictionaries}
    while (new_id := random.getrandbits(64)) in ids or new_id == 0:
        pass
    d = Dictionary(id=new_id, name=name)
    storage.dictionaries.append(d)
    logger.info(f"created dictionary {name!r} (id={new_id})")
    return d


def reload_server(dry_run: bool) -> int:
    cmd = ["pkill", "-x", "-U", str(os.getuid()), "mozc_server"]  # -U: don't touch other users' mozc_server
    if dry_run:
        print(shlex.join(cmd))
        return 0
    logger.info(shlex.join(cmd))
    res = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if res.stderr:  # pkill exits 0 even when kill(2) fails (e.g. Operation not permitted)
        logger.error(f"pkill: {res.stderr.strip()}")
        return 1
    if res.returncode == 0:
        logger.info("mozc_server killed; it restarts automatically on next IME use and reloads the dictionary")
    elif res.returncode == 1:
        logger.info("mozc_server is not running; nothing to do")
    else:
        logger.error(f"pkill failed with exit code {res.returncode}")
        return res.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog,
                                     description="edit the mozc user dictionary (~/.config/mozc/user_dictionary.db) from the command line")
    parser.add_argument("-q", "--quiet", action="count", default=0,
                        help="decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error")
    parser.add_argument("-n", "--dry_run", action="store_true", help="print commands instead of executing (reload)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="user dictionary file")
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    subparser = subparsers.add_parser("dicts", formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                      help="list dictionaries")
    subparser.set_defaults(func=cmd_dicts)

    subparser = subparsers.add_parser("list", formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                      help="print entries as TSV (よみ 単語 品詞 コメント)")
    subparser.set_defaults(func=cmd_list)
    subparser.add_argument("--dict", help="dictionary name; default: all")

    subparser = subparsers.add_parser("add", formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                      help="add one word")
    subparser.set_defaults(func=cmd_add)
    subparser.add_argument("reading", help="よみ (ひらがな)")
    subparser.add_argument("word", help="単語")
    subparser.add_argument("--pos", default="名詞", help="品詞 (日本語名 or enum 名)")
    subparser.add_argument("--comment", default="")
    subparser.add_argument("--dict", help="dictionary name; default: first one (created if none)")
    subparser.add_argument("--reload", action="store_true", help="kill mozc_server afterwards to reload")

    subparser = subparsers.add_parser("import", formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                      help="add words from TSV (よみ<TAB>単語[<TAB>品詞[<TAB>コメント]]); '-' for stdin")
    subparser.set_defaults(func=cmd_import)
    subparser.add_argument("tsv", type=argparse.FileType("r"))
    subparser.add_argument("--dict", help="dictionary name; default: first one (created if none)")
    subparser.add_argument("--reload", action="store_true", help="kill mozc_server afterwards to reload")

    subparser = subparsers.add_parser("remove", formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                      help="remove entries matching the reading (and word if given)")
    subparser.set_defaults(func=cmd_remove)
    subparser.add_argument("reading")
    subparser.add_argument("word", nargs="?")
    subparser.add_argument("--dict", help="dictionary name; default: all")
    subparser.add_argument("--reload", action="store_true", help="kill mozc_server afterwards to reload")

    subparser = subparsers.add_parser("reload", formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                      help="kill mozc_server so it reloads the dictionary on next use")
    subparser.set_defaults(func=cmd_reload)

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f"{args=}")
    return args.func(args)


def cmd_dicts(args: argparse.Namespace) -> int:
    storage = load_storage(args.db)
    for d in storage.dictionaries:
        print(f"{d.name}\t{len(d.entries)} entries\tid={d.id}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    storage = load_storage(args.db)
    dicts = storage.dictionaries if args.dict is None else [find_dictionary(storage, args.dict, create=False)]
    for d in dicts:
        logger.info(f"dictionary: {d.name} ({len(d.entries)} entries)")
        for e in d.entries:
            print(f"{e.key}\t{e.value}\t{e.pos_ja()}\t{e.comment or ''}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    if not args.reading or not args.word:
        raise SystemExit("reading and word must be non-empty")
    storage = load_storage(args.db)
    d = find_dictionary(storage, args.dict, create=True)
    d.entries.append(Entry(key=args.reading, value=args.word, comment=args.comment, pos=pos_from_str(args.pos)))
    save_storage(args.db, storage)
    logger.info(f"added: {args.reading} -> {args.word} [{POS_JA_BY_NUM[pos_from_str(args.pos)]}] to {d.name!r}")
    return reload_server(args.dry_run) if args.reload else 0


def cmd_import(args: argparse.Namespace) -> int:
    storage = load_storage(args.db)
    d = find_dictionary(storage, args.dict, create=True)
    n = 0
    for lineno, line in enumerate(args.tsv, 1):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 2 or not cols[0] or not cols[1]:
            raise SystemExit(f"line {lineno}: expected よみ<TAB>単語[<TAB>品詞[<TAB>コメント]]: {line!r}")
        d.entries.append(Entry(key=cols[0], value=cols[1],
                               comment=cols[3] if len(cols) > 3 else "",
                               pos=pos_from_str(cols[2] if len(cols) > 2 else "")))
        n += 1
    save_storage(args.db, storage)
    logger.info(f"imported {n} entries into {d.name!r}")
    return reload_server(args.dry_run) if args.reload else 0


def cmd_remove(args: argparse.Namespace) -> int:
    storage = load_storage(args.db)
    dicts = storage.dictionaries if args.dict is None else [find_dictionary(storage, args.dict, create=False)]
    n = 0
    for d in dicts:
        kept = [e for e in d.entries if not (e.key == args.reading and args.word in (None, e.value))]
        n += len(d.entries) - len(kept)
        d.entries = kept
    if n == 0:
        logger.warning(f"no entry matched: {args.reading}" + (f" {args.word}" if args.word else ""))
        return 1
    save_storage(args.db, storage)
    logger.info(f"removed {n} entries")
    return reload_server(args.dry_run) if args.reload else 0


def cmd_reload(args: argparse.Namespace) -> int:
    return reload_server(args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
