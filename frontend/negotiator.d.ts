declare module "negotiator" {
  type NegotiatorOptions = {
    headers?: Record<string, string | string[] | undefined>;
  };

  export default class Negotiator {
    constructor(options?: NegotiatorOptions);
    languages(availableLanguages?: string[]): string[];
  }
}
