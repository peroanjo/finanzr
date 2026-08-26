export type MessageTree = {
  readonly [key: string]: string | MessageTree;
};

export type TranslationFor<Source> = {
  readonly [Key in keyof Source]: Source[Key] extends string
    ? string
    : Source[Key] extends MessageTree
      ? TranslationFor<Source[Key]>
      : never;
};

/**
 * Defines an English source catalog and its complete Spanish translation.
 * Keeping English as the first argument makes the source/fallback contract explicit,
 * while the mapped type prevents translations from drifting out of shape.
 */
export function defineMessageCatalog<const English extends MessageTree>(
  en: English,
  esES: TranslationFor<English>,
) {
  return { en, "es-ES": esES } as const;
}
