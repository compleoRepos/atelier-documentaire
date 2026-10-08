import { Injectable, signal } from "@angular/core";
@Injectable({ providedIn: "root" })
export class ErrorService {
  readonly message = signal<string | null>(null);
  private timer: ReturnType<typeof setTimeout> | undefined;
  show(message: string): void {
    this.message.set(message);
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.message.set(null), 8000);
  }
  clear(): void {
    this.message.set(null);
  }
}
