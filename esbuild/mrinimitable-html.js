module.exports = {
	name: "mrinimitable-html",
	setup(build) {
		let path = require("path");
		let fs = require("fs/promises");

		build.onResolve({ filter: /\.html$/ }, (args) => {
			return {
				path: path.join(args.resolveDir, args.path),
				namespace: "mrinimitable-html",
			};
		});

		build.onLoad({ filter: /.*/, namespace: "mrinimitable-html" }, (args) => {
			let filepath = args.path;
			let filename = path.basename(filepath).split(".")[0];

			return fs
				.readFile(filepath, "utf-8")
				.then((content) => {
					content = scrub_html_template(content);
					return {
						contents: `\n\tmrinimitable.templates['${filename}'] = \`${content}\`;\n`,
						watchFiles: [filepath],
					};
				})
				.catch(() => {
					return {
						contents: "",
						warnings: [
							{
								text: `There was an error importing ${filepath}`,
							},
						],
					};
				});
		});
	},
};

function scrub_html_template(content) {
	content = content.replace(/`/g, "\\`");
	return content;
}
