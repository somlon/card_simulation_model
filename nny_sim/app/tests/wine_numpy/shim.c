/* 시험 전용(배포본에 넣지 않음) — make_test_copy.py 가 쓴다. wine 9.0 의 ucrtbase 에 없는 C99 복소수 함수를 채우고, 나머지 수학 함수는 shim.def 에서 ucrtbase 로 넘긴다.
   Windows UCRT 의 _Fcomplex · _Dcomplex 는 구조체 — MS x64 호출 규약(8바이트 구조체 = 레지스터, 16바이트 = 포인터 · 숨은 반환 포인터)을 GCC 구조체로 맞춘다 */
#include <math.h>
typedef struct { float re, im; } fcx;
typedef struct { double re, im; } dcx;
#define F(name) __declspec(dllexport) name
F(float crealf)(fcx z) { return z.re; }
F(float cimagf)(fcx z) { return z.im; }
F(float cabsf)(fcx z) { return hypotf(z.re, z.im); }
F(float cargf)(fcx z) { return atan2f(z.im, z.re); }
static fcx fmk(float a, float b) { fcx r = {a, b}; return r; }
F(fcx cexpf)(fcx z) { float e = expf(z.re); return fmk(e * cosf(z.im), e * sinf(z.im)); }
F(fcx cpowf)(fcx a, fcx b) { if (a.re == 0 && a.im == 0) return fmk(0, 0); float lr = logf(hypotf(a.re, a.im)), th = atan2f(a.im, a.re);
  float re = b.re * lr - b.im * th, im = b.im * lr + b.re * th, e = expf(re); return fmk(e * cosf(im), e * sinf(im)); }
F(fcx csinf)(fcx z) { return fmk(sinf(z.re) * coshf(z.im), cosf(z.re) * sinhf(z.im)); }
F(fcx ccosf)(fcx z) { return fmk(cosf(z.re) * coshf(z.im), -sinf(z.re) * sinhf(z.im)); }
F(fcx csinhf)(fcx z) { return fmk(sinhf(z.re) * cosf(z.im), coshf(z.re) * sinf(z.im)); }
F(fcx ccoshf)(fcx z) { return fmk(coshf(z.re) * cosf(z.im), sinhf(z.re) * sinf(z.im)); }
F(fcx ctanf)(fcx z) { float d = cosf(2 * z.re) + coshf(2 * z.im); return fmk(sinf(2 * z.re) / d, sinhf(2 * z.im) / d); }
F(fcx ctanhf)(fcx z) { float d = coshf(2 * z.re) + cosf(2 * z.im); return fmk(sinhf(2 * z.re) / d, sinf(2 * z.im) / d); }
static dcx dmk(double a, double b) { dcx r = {a, b}; return r; }
F(double creal)(dcx z) { return z.re; }
F(double cimag)(dcx z) { return z.im; }
F(double carg)(dcx z) { return atan2(z.im, z.re); }
F(double creall)(dcx z) { return z.re; }
F(double cimagl)(dcx z) { return z.im; }
F(double cargl)(dcx z) { return atan2(z.im, z.re); }
F(double cabsl)(dcx z) { return hypot(z.re, z.im); }
F(dcx cexp)(dcx z) { double e = exp(z.re); return dmk(e * cos(z.im), e * sin(z.im)); }
F(dcx cexpl)(dcx z) { return cexp(z); }
F(dcx cpow)(dcx a, dcx b) { if (a.re == 0 && a.im == 0) return dmk(0, 0); double lr = log(hypot(a.re, a.im)), th = atan2(a.im, a.re);
  double re = b.re * lr - b.im * th, im = b.im * lr + b.re * th, e = exp(re); return dmk(e * cos(im), e * sin(im)); }
F(dcx cpowl)(dcx a, dcx b) { return cpow(a, b); }
F(dcx csin)(dcx z) { return dmk(sin(z.re) * cosh(z.im), cos(z.re) * sinh(z.im)); }
F(dcx ccos)(dcx z) { return dmk(cos(z.re) * cosh(z.im), -sin(z.re) * sinh(z.im)); }
F(dcx csinh)(dcx z) { return dmk(sinh(z.re) * cos(z.im), cosh(z.re) * sin(z.im)); }
F(dcx ccosh)(dcx z) { return dmk(cosh(z.re) * cos(z.im), sinh(z.re) * sin(z.im)); }
F(dcx ctan)(dcx z) { double d = cos(2 * z.re) + cosh(2 * z.im); return dmk(sin(2 * z.re) / d, sinh(2 * z.im) / d); }
F(dcx ctanh)(dcx z) { double d = cosh(2 * z.re) + cos(2 * z.im); return dmk(sinh(2 * z.re) / d, sin(2 * z.im) / d); }
F(dcx csinl)(dcx z) { return csin(z); } F(dcx ccosl)(dcx z) { return ccos(z); } F(dcx csinhl)(dcx z) { return csinh(z); }
F(dcx ccoshl)(dcx z) { return ccosh(z); } F(dcx ctanl)(dcx z) { return ctan(z); } F(dcx ctanhl)(dcx z) { return ctanh(z); }
