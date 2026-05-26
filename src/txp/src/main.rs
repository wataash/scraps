// SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
// SPDX-License-Identifier: Apache-2.0

use clap::Parser;
use std::fs;
use std::io::{self, Read, Write};
use std::path::PathBuf;
use std::process::ExitCode;
use txp::txp;

#[derive(Debug, Parser)]
#[command(
    name = "txp",
    about = "Remove private marker comments from text.",
    long_about = "Remove private marker comments from text.\n\nIf FILE is omitted, txp reads from standard input and writes to standard output."
)]
struct Args {
    #[arg(long)]
    preserve_plp: bool,

    /// Input file. Reads from standard input when omitted
    #[arg(value_name = "FILE")]
    file: Option<PathBuf>,
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("txp: {err}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), String> {
    let args = Args::parse();
    let txt = match args.file {
        Some(file) => {
            fs::read_to_string(&file).map_err(|err| format!("{}: {err}", file.display()))?
        }
        None => {
            let mut txt = String::new();
            io::stdin()
                .read_to_string(&mut txt)
                .map_err(|err| format!("stdin: {err}"))?;
            txt
        }
    };

    let out = txp(&txt, args.preserve_plp);
    io::stdout()
        .write_all(out.as_bytes())
        .map_err(|err| format!("stdout: {err}"))?;
    Ok(())
}
