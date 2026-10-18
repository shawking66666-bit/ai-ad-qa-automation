from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


class WindowsLauncherTests(unittest.TestCase):
    def test_start_cmd_invokes_powershell_launcher_from_its_own_directory(self):
        content = read_project_file("启动FastAPI.cmd")

        self.assertIn("%~dp0", content)
        self.assertIn("start_video_processor.ps1", content)
        self.assertIn("-ExecutionPolicy Bypass", content)

    def test_stop_cmd_invokes_scoped_stop_script(self):
        content = read_project_file("停止FastAPI.cmd")

        self.assertIn("%~dp0", content)
        self.assertIn("stop_video_processor.ps1", content)

    def test_health_check_cmd_checks_local_health_endpoint(self):
        content = read_project_file("检查FastAPI状态.cmd")

        self.assertIn("http://localhost:8000/health", content)
        self.assertIn("health_check_video_processor.ps1", content)

    def test_start_script_creates_data_directory_and_checks_dependencies(self):
        content = read_project_file("start_video_processor.ps1")

        self.assertIn("E:\\AI\\Data\\AI-Ad-QA\\video_processor_data", content)
        self.assertIn("New-Item", content)
        self.assertIn("requirements.txt", content)
        self.assertIn("video_processor.app:app", content)
        self.assertIn(".venv\\Scripts\\python.exe", content)
        self.assertIn("VIDEO_PROCESSOR_FFMPEG_PATH", content)
        self.assertIn("VIDEO_PROCESSOR_FFPROBE_PATH", content)
        self.assertNotIn("python -m pip install", content)

    def test_start_script_does_not_treat_python_stderr_warning_as_failure(self):
        content = read_project_file("start_video_processor.ps1")

        self.assertIn('$ErrorActionPreference = "Continue"', content)
        self.assertIn("$dependencyCheckExitCode = $LASTEXITCODE", content)
        self.assertIn("$runtimeCheckExitCode = $LASTEXITCODE", content)
        self.assertIn("$serverExitCode = $LASTEXITCODE", content)

    def test_gitignore_excludes_secrets_media_and_runtime_outputs(self):
        content = read_project_file(".gitignore")

        for expected in (".env", ".venv/", "__pycache__/", "outputs/", "*.mp4", "*.mov"):
            self.assertIn(expected, content)

    def test_github_initializer_uses_repository_local_identity_and_private_remote(self):
        content = read_project_file("Push-to-GitHub.cmd")

        self.assertIn('git config --global --add safe.directory "%CD%"', content)
        self.assertIn("git config --local user.name shawking66666-bit", content)
        self.assertIn(
            "git config --local user.email "
            "272393408+shawking66666-bit@users.noreply.github.com",
            content,
        )
        self.assertIn(
            "https://github.com/shawking66666-bit/ai-ad-qa-automation.git",
            content,
        )
        self.assertIn("git push -u origin main", content)


if __name__ == "__main__":
    unittest.main()
