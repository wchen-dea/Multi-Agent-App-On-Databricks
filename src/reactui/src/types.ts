export type Role = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
}

export interface StreamHints {
  categories: Set<string>;
  tools: Set<string>;
}

export interface FrontendSettings {
  backendUrl: string;
  chatGreeting: string;
  timeoutSeconds: number;
  companyName: string;
  companyTagline: string;
  forwardedAccessTokenHeader: string;
  setTokenCommand: string;
  clearTokenCommand: string;
  setPersonaCommand: string;
  clearPersonaCommand: string;
  allowedPersonas: string[];
}