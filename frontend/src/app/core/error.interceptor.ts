import { HttpErrorResponse, HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";
import { catchError, throwError } from "rxjs";
import { ErrorService } from "./error.service";
export const errorInterceptor: HttpInterceptorFn = (request, next) =>
  next(request).pipe(
    catchError((error: HttpErrorResponse) => {
      const notice = inject(ErrorService);
      const detail =
        typeof error.error?.detail === "string"
          ? error.error.detail
          : "Le service documentaire est momentanément indisponible.";
      if (error.status !== 401 || request.url.includes("/auth/login"))
        notice.show(detail);
      return throwError(() => error);
    })
  );
