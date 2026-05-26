// SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
// SPDX-License-Identifier: Apache-2.0

pub fn txp(txt: &str, preserve_plp: bool) -> String {
    let mut pieces = split_lines_keep_ends(txt);

            C
            "#,
            false,
            r#"
            A
            C
            "#,
        );
    }

    #[test]
    fn removes_line_above_marker() {
        assert_txp(
            r#"
            A
            C
            "#,
            false,
            r#"
            A
            C
            "#,
        );
    }

    #[test]
    fn keeps_pla_at_first_line_like_node_regex() {
        let input = heredoc(
            B
            "#,
        );
        assert_eq!(txp(&input, false), input);
    }

    #[test]
    fn removes_line_below_marker() {
        assert_txp(
            r#"
            A
            C
            "#,
            false,
            r#"
            A
            C
            "#,
        );
    }

    #[test]
    fn keeps_plb_at_eof_without_newline_like_node_regex() {
        let input = heredoc_no_nl(
            r#"
            A
        );
        assert_eq!(txp(&input, false), input);
    }

    #[test]
    fn removes_plb_at_eof_with_newline() {
        assert_txp(
            r#"
            A
            false,
            r#"
            A
            "#,
        );
    }

    #[test]
    fn removes_right_marker_and_line_break() {
        assert_txp(
            r#"
            A
            B            C
            "#,
            false,
            r#"
            A
            BC
            "#,
        );
    }

    #[test]
    fn removes_right_comment_marker_and_line_break() {
        assert_txp(
            r#"
            A
            B            C
            "#,
            false,
            r#"
            A
            BC
            "#,
        );
    }

    #[test]
    fn removes_right_hash_comment_marker_and_line_break() {
        assert_txp(
            r#"
            A
            B            C
            "#,
            false,
            r#"
            A
            BC
            "#,
        );
    }

    #[test]
    fn removes_publish_private_markers_by_default() {
        assert_txp(
            r#"
            A
            C
            D            E
            "#,
            false,
            r#"
            A
            C
            DE
            "#,
        );
    }

    #[test]
    fn preserves_publish_private_markers_when_requested() {
        let input = heredoc(
            r#"
            A
            C
            D            E
            "#,
        );
        assert_eq!(txp(&input, true), input);
    }

    #[test]
    fn handles_crlf() {
    }

    #[test]
    fn handles_eof_without_trailing_newline() {
        assert_txp_no_nl(
            r#"
            A
            B
            "#,
            false,
            r#"
            A
            B
            "#,
        );
    }

    #[test]
    fn handles_empty_input() {
        assert_eq!(txp("", false), "");
    }

    #[test]
    fn keeps_unmatched_begin_block() {
        let input = heredoc(
            r#"
            A
            // @bv
            B
            C
            "#,
        );
        assert_eq!(txp(&input, false), input);
    }

    #[test]
    fn matches_marker_after_earlier_non_boundary_hit() {
        assert_txp(
            r#"
            A
            B
            "#,
            false,
            r#"
            A
            B
            "#,
        );
    }

    #[test]
    fn marker_boundary_rejects_longer_marker_name() {
        let input = heredoc(
            r#"
            A
            // @plxyz x
            B
            "#,
        );
        assert_eq!(txp(&input, false), input);
    }
}
