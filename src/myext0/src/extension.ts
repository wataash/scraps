// The module 'vscode' contains the VS Code extensibility API
// Import the module and reference it with the alias vscode in your code below
import * as vscode from 'vscode';

// This method is called when your extension is activated
// Your extension is activated the very first time the command is executed
export function activate(context: vscode.ExtensionContext) {

	// Use the console to output diagnostic information (console.log) and errors (console.error)
	// This line of code will only be executed once when your extension is activated
	console.log('Congratulations, your extension "myext0" is now active!');

	// The command has been defined in the package.json file
	// Now provide the implementation of the command with registerCommand
	// The commandId parameter must match the command field in package.json
	const disposable = vscode.commands.registerCommand('myext0.helloWorld', () => {
		// The code you place here will be executed every time your command is executed
		// Display a message box to the user
		vscode.window.showInformationMessage('myext0 Hello World from MyExt0!');
	});

	context.subscriptions.push(disposable);

	// カーソルがいるフェンスドコードブロックの中身（フェンス行を除く）をコピーする
	const copyCodeBlock = vscode.commands.registerCommand('myext0.copyCodeBlock', async () => {
		const editor = vscode.window.activeTextEditor;
		if (!editor) { return; }
		const doc = editor.document;
		const lines: string[] = [];
		for (let i = 0; i < doc.lineCount; i++) {
			lines.push(doc.lineAt(i).text);
		}
		const body = extractCodeBlock(lines, editor.selection.active.line);
		if (body === undefined) {
			vscode.window.showWarningMessage('Cursor is not inside a code block');
			return;
		}
		await vscode.env.clipboard.writeText(body);
		const count = body === '' ? 0 : body.split('\n').length;
		vscode.window.showInformationMessage(`Copied code block (${count} lines)`);
	});

	context.subscriptions.push(copyCodeBlock);

	// 現在のエディタのインデント設定を直接変更する（"Indent Using Spaces/Tabs" のクイックピックと同じ効果。
	// ユーザー設定は書き換えず、そのファイルのモデルオプションだけを変更する）。
	// editor.action.indentUsingSpaces/Tabs は引数を取れず quick pick が出る (vscode#218412 not planned) ため自作。
	const setIndent = vscode.commands.registerCommand(
		'myext0.setIndent',
		(args: SetIndentArgs | undefined) => {
			const editor = vscode.window.activeTextEditor;
			const options = buildIndentOptions(args);
			if (!editor || !options) { return; }
			editor.options = options;
		},
	);

	context.subscriptions.push(setIndent);
}

export interface SetIndentArgs {
	insertSpaces?: boolean;
	tabSize?: number;
}

/**
 * myext0.setIndent の引数から TextEditor.options に渡すオプションを組み立てる。
 * args が無いときは undefined（何もしない）を返す。
 * tabSize は数値のときだけ設定し、それ以外（タブ指定など）は現在の値を維持する。
 */
export function buildIndentOptions(
	args: SetIndentArgs | undefined,
): { insertSpaces: boolean; tabSize?: number } | undefined {
	if (!args) { return undefined; }
	const options: { insertSpaces: boolean; tabSize?: number } = { insertSpaces: !!args.insertSpaces };
	if (typeof args.tabSize === 'number') { options.tabSize = args.tabSize; }
	return options;
}

const FENCE = /^\s*(`{3,}|~{3,})/; // ``` または ~~~ (3個以上)

/**
 * lines のうち cursorLine がいるフェンスドコードブロックの中身（フェンス行を除く）を返す。
 * カーソルがどのブロックの中にも無い場合は undefined を返す。
 */
export function extractCodeBlock(lines: string[], cursorLine: number): string | undefined {
	// カーソル行から上方向に開きフェンスを探す
	let open = -1;
	for (let i = cursorLine; i >= 0; i--) {
		if (FENCE.test(lines[i])) { open = i; break; }
	}
	if (open === -1) { return undefined; }
	// 開きフェンスの下方向に閉じフェンスを探す
	let close = -1;
	for (let i = open + 1; i < lines.length; i++) {
		if (FENCE.test(lines[i])) { close = i; break; }
	}
	if (close === -1 || cursorLine > close) { return undefined; }
	return lines.slice(open + 1, close).join('\n');
}

// This method is called when your extension is deactivated
export function deactivate() {}
