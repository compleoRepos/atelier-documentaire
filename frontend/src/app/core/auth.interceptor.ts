import { HttpInterceptorFn } from "@angular/common/http";
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const csrf = readCookie("translator_csrf");
  const mutating = ["POST", "PUT", "PATCH", "DELETE"].includes(
    request.method.toUpperCase()
  );
  const headers =
    mutating && csrf ? { "X-CSRF-Token": csrf } : undefined;
  return next(
    request.clone({
      withCredentials: true,
      ...(headers ? { setHeaders: headers } : {}),
    })
  );
};

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${encodeURIComponent(name)}=`;
  const value = document.cookie
    .split(";")
    .map(item => item.trim())
    .find(item => item.startsWith(prefix));
  if (!value) return null;
  try {
    return decodeURIComponent(value.slice(prefix.length));
  } catch {
    return value.slice(prefix.length);
  }
}
