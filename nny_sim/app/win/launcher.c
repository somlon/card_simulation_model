/* NNY 시뮬레이터 실행기 — 같은 폴더의 runtime\pythonw.exe 로 app\main.py 를 띄운다(콘솔 창 없음).
   빌드(리눅스): x86_64-w64-mingw32-gcc -municode -mwindows -O2 launcher.c resource.o -o NNY_Simulator.exe */
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

static void fail(const wchar_t *what, const wchar_t *path) {
    wchar_t msg[2048];
    swprintf(msg, 2048, L"%ls\n\n%ls\n\n프로그램 폴더를 통째로 압축 해제했는지 확인해 주세요.", what, path);
    MessageBoxW(NULL, msg, L"NNY 시뮬레이터", MB_ICONERROR | MB_OK);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR args, int show) {
    wchar_t dir[MAX_PATH], py[MAX_PATH], script[MAX_PATH], cmd[4096];
    DWORD n = GetModuleFileNameW(NULL, dir, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) { fail(L"실행 파일 경로를 읽지 못했습니다.", L""); return 1; }
    wchar_t *slash = wcsrchr(dir, L'\\'); if (slash) *slash = 0;
    swprintf(py, MAX_PATH, L"%ls\\runtime\\pythonw.exe", dir);
    swprintf(script, MAX_PATH, L"%ls\\app\\main.py", dir);
    if (GetFileAttributesW(py) == INVALID_FILE_ATTRIBUTES) { fail(L"파이썬 실행 파일이 없습니다:", py); return 1; }
    if (GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) { fail(L"프로그램 파일이 없습니다:", script); return 1; }
    /* -I: 사용자 환경(PYTHONPATH 등)과 분리, -X utf8: 한글 경로 · 파일을 UTF-8 로 */
    swprintf(cmd, 4096, L"\"%ls\" -I -X utf8 \"%ls\" %ls", py, script, args ? args : L"");
    STARTUPINFOW si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof si); si.cb = sizeof si; ZeroMemory(&pi, sizeof pi);
    if (!CreateProcessW(py, cmd, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi)) { fail(L"프로그램을 시작하지 못했습니다:", py); return 1; }
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    return 0;
}
