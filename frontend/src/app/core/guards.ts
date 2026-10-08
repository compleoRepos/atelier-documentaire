import { inject } from "@angular/core";
import { CanActivateFn, Router } from "@angular/router";
import { map } from "rxjs/operators";
import { AuthService } from "./auth.service";
export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.restore().pipe(
    map(user =>
      user
        ? true
        : router.createUrlTree(["/login"], {
            queryParams: { returnUrl: state.url },
          })
    )
  );
};
export const roleGuard =
  (roles: string[]): CanActivateFn =>
  (_route, state) => {
    const auth = inject(AuthService);
    const router = inject(Router);
    return auth.restore().pipe(
      map(() =>
        auth.hasRole(roles)
          ? true
          : router.createUrlTree(["/dashboard"], {
              queryParams: { denied: state.url },
            })
      )
    );
  };
