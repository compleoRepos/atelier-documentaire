import { bootstrapApplication } from "@angular/platform-browser";
import { provideAppInitializer, inject } from "@angular/core";
import { provideHttpClient, withInterceptors } from "@angular/common/http";
import { provideRouter, withComponentInputBinding } from "@angular/router";
import { AppComponent } from "./app/app.component";
import { appRoutes } from "./app/app.routes";
import { AuthService } from "./app/core/auth.service";
import { authInterceptor } from "./app/core/auth.interceptor";
import { errorInterceptor } from "./app/core/error.interceptor";

bootstrapApplication(AppComponent, {
  providers: [
    provideRouter(appRoutes, withComponentInputBinding()),
    provideHttpClient(withInterceptors([authInterceptor, errorInterceptor])),
    provideAppInitializer(() => inject(AuthService).restore()),
  ],
}).catch((error: unknown) =>
  console.error("Bootstrap Angular impossible", error)
);
