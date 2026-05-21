/** Re-export internal helpers from QualifsPage for unit testing.
 *
 * Keeping production code clean of test-only exports — this file is the
 * single entry point tests import from, so the production file stays
 * focused on the page behaviour. */
export { CommentEditor } from "./QualifsPage";
