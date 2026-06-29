import * as assert from 'assert';

// You can import and use all API from the 'vscode' module
// as well as import your extension to test it
import * as vscode from 'vscode';
import { extractCodeBlock, buildIndentOptions } from '../extension';

suite('Extension Test Suite', () => {
	vscode.window.showInformationMessage('Start all tests.');

	suite('extractCodeBlock', () => {
		const block = [
			'```',            // 0
			'code 1 line 1',  // 1
			'code 1 line 2',  // 2
			'```',            // 3
		];

		test('カーソルがブロック内のとき中身を返す', () => {
			assert.strictEqual(extractCodeBlock(block, 1), 'code 1 line 1\ncode 1 line 2');
			assert.strictEqual(extractCodeBlock(block, 2), 'code 1 line 1\ncode 1 line 2');
		});

		test('カーソルが開きフェンス行のとき中身を返す', () => {
			assert.strictEqual(extractCodeBlock(block, 0), 'code 1 line 1\ncode 1 line 2');
		});

		test('言語指定付きフェンスでも言語は除外して中身を返す', () => {
			const langBlock = [
				'```sh',          // 0
				'code 1 line 1',  // 1
				'code 1 line 2',  // 2
				'```',            // 3
			];
			assert.strictEqual(extractCodeBlock(langBlock, 1), 'code 1 line 1\ncode 1 line 2');
			assert.strictEqual(extractCodeBlock(langBlock, 0), 'code 1 line 1\ncode 1 line 2');
		});

		test('~~~ フェンスにも対応する', () => {
			const tildeBlock = [
				'~~~',            // 0
				'code 1 line 1',  // 1
				'code 1 line 2',  // 2
				'~~~',            // 3
			];
			assert.strictEqual(extractCodeBlock(tildeBlock, 1), 'code 1 line 1\ncode 1 line 2');
		});

		test('インデントされたフェンスにも対応する', () => {
			const indented = [
				'  ```',          // 0
				'  code',         // 1
				'  ```',          // 2
			];
			assert.strictEqual(extractCodeBlock(indented, 1), '  code');
		});

		test('空のブロックは空文字を返す', () => {
			assert.strictEqual(extractCodeBlock(['```', '```'], 0), '');
		});

		test('ブロック外（閉じフェンスより下）では undefined を返す', () => {
			const doc = [
				'```',            // 0
				'code 1 line 1',  // 1
				'```',            // 2
				'outside',        // 3
			];
			assert.strictEqual(extractCodeBlock(doc, 3), undefined);
		});

		test('コードブロックが無いとき undefined を返す', () => {
			assert.strictEqual(extractCodeBlock(['just text', 'no fence'], 0), undefined);
		});

		test('開きフェンスだけで閉じフェンスが無いとき undefined を返す', () => {
			assert.strictEqual(extractCodeBlock(['```', 'code'], 1), undefined);
		});
	});

	suite('buildIndentOptions', () => {
		test('スペース＋サイズ指定でそのオプションを返す', () => {
			assert.deepStrictEqual(buildIndentOptions({ insertSpaces: true, tabSize: 2 }), { insertSpaces: true, tabSize: 2 });
			assert.deepStrictEqual(buildIndentOptions({ insertSpaces: true, tabSize: 9 }), { insertSpaces: true, tabSize: 9 });
		});

		test('タブ＋サイズ指定でそのオプションを返す', () => {
			assert.deepStrictEqual(buildIndentOptions({ insertSpaces: false, tabSize: 8 }), { insertSpaces: false, tabSize: 8 });
			assert.deepStrictEqual(buildIndentOptions({ insertSpaces: false, tabSize: 4 }), { insertSpaces: false, tabSize: 4 });
		});

		test('タブ指定（tabSize なし）では tabSize を含めず現在値を維持する', () => {
			assert.deepStrictEqual(buildIndentOptions({ insertSpaces: false }), { insertSpaces: false });
		});

		test('insertSpaces 省略時は false 扱い', () => {
			assert.deepStrictEqual(buildIndentOptions({ tabSize: 4 }), { insertSpaces: false, tabSize: 4 });
		});

		test('args が undefined のときは undefined を返す', () => {
			assert.strictEqual(buildIndentOptions(undefined), undefined);
		});
	});

	suite('myext0.setIndent コマンド', () => {
		test('スペース・サイズを設定するとアクティブエディタのオプションが変わる', async () => {
			const doc = await vscode.workspace.openTextDocument({ content: 'hello\nworld\n' });
			const editor = await vscode.window.showTextDocument(doc);

			await vscode.commands.executeCommand('myext0.setIndent', { insertSpaces: true, tabSize: 3 });
			assert.strictEqual(editor.options.insertSpaces, true);
			assert.strictEqual(editor.options.tabSize, 3);

			await vscode.commands.executeCommand('myext0.setIndent', { insertSpaces: false, tabSize: 8 });
			assert.strictEqual(editor.options.insertSpaces, false);
			assert.strictEqual(editor.options.tabSize, 8);
		});
	});
});
