import { FlatCompat } from "@eslint/eslintrc";
const compat = new FlatCompat({ baseDirectory: import.meta.dirname });
export default [
  { ignores: [".next/**", "node_modules/**", "src/generated/**"] },
  ...compat.extends("next/core-web-vitals", "next/typescript", "prettier"),
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      // UI/route layers must never reach Prisma directly (CLAUDE.md §4)
      "no-restricted-imports": ["error", { patterns: [{ group: ["@prisma/client"], message: "Use src/server/repos only." }] }],
    },
  },
  {
    files: ["src/server/repos/**", "src/server/db/**", "prisma/**", "src/worker/**", "tests/**"],
    rules: { "no-restricted-imports": "off" },
  },
];
