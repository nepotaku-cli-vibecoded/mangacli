using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;

class MangaLauncher
{
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr GetStdHandle(int nStdHandle);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetConsoleDisplayMode(IntPtr hConsoleOutput, uint dwFlags, out int lpNewScreenBufferDimensions);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetConsoleScreenBufferSize(IntPtr hConsoleOutput, COORD dwSize);

    [DllImport("user32.dll", SetLastError = true)]
    static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("kernel32.dll")]
    static extern IntPtr GetConsoleWindow();

    struct COORD { public short X, Y; }

    const int STD_OUTPUT_HANDLE = -11;
    const uint CONSOLE_FULLSCREEN_MODE = 1;
    const int SW_MAXIMIZE = 3;

    static void Main()
    {
        IntPtr handle = GetStdHandle(STD_OUTPUT_HANDLE);

        int newSize;
        if (!SetConsoleDisplayMode(handle, CONSOLE_FULLSCREEN_MODE, out newSize))
        {
            IntPtr consoleWnd = GetConsoleWindow();
            if (consoleWnd != IntPtr.Zero)
                ShowWindow(consoleWnd, SW_MAXIMIZE);
        }

        try { SetConsoleScreenBufferSize(handle, new COORD { X = 180, Y = 9001 }); } catch { }

        Thread.Sleep(300);

        var psi = new ProcessStartInfo
        {
            FileName = "python",
            Arguments = "-m mangacli",
            UseShellExecute = false,
        };

        try
        {
            using (var p = Process.Start(psi))
            {
                if (p != null) p.WaitForExit();
            }
        }
        catch
        {
            psi.FileName = "python3";
            try
            {
                using (var p = Process.Start(psi))
                {
                    if (p != null) p.WaitForExit();
                }
            }
            catch
            {
                Console.WriteLine("Could not find Python. Make sure it's installed and on PATH.");
                Console.ReadKey();
            }
        }
    }
}
