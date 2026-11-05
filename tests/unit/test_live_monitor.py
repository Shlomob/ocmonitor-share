import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from ocmonitor.config import PathsConfig
from ocmonitor.services.live_monitor import LiveMonitor


class TestLiveMonitorDisplayMode:
    """Tests for Rich Live full-screen and inline setup."""

    @staticmethod
    def _record_live_instances(monkeypatch):
        """Replace Rich Live and return every instance created by a monitor."""
        live_instances = []

        class FakeLive:
            """A minimal context manager used to mimic Rich Live in tests.

            Instances are appended to the outer `live_instances` list and
            construction kwargs are captured for assertions.
            """
            def __init__(self, *args, **kwargs):
                """Initialize the fake live instance and record the kwargs.

                The instance is appended to the enclosing `live_instances` list
                so tests can assert how the Live context was constructed.
                """
                self.kwargs = kwargs
                live_instances.append(self)

            def __enter__(self):
                """Enter the context manager and return this instance."""
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                """Exit the context manager and do not suppress exceptions.

                Returning False ensures any exception (e.g., KeyboardInterrupt)
                propagates to the test.
                """
                return False

        monkeypatch.setattr("ocmonitor.services.live_monitor.Live", FakeLive)
        return live_instances

    def test_file_monitor_uses_full_screen_by_default_and_inline_when_requested(
        self, monkeypatch, tmp_path
    ):
        """Verify file-based LiveMonitor uses full-screen by default and inline when requested.

        The test asserts that the Live context is created with `screen=True` for the
        default call and `screen=False` when invoked with `inline=True`.
        """
        workflow = SimpleNamespace(
            workflow_id="file-workflow",
            main_session=SimpleNamespace(session_id="file-session", files=[]),
            all_sessions=[SimpleNamespace(session_id="file-session")],
            has_sub_agents=False,
            display_title="File workflow",
            project_name="project",
            session_count=1,
            sub_agent_count=0,
        )
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)
        monkeypatch.setattr(
            monitor, "_get_file_active_workflows", lambda *args, **kwargs: [workflow]
        )
        monkeypatch.setattr(monitor, "_generate_workflow_dashboard", lambda *args: None)
        live_instances = self._record_live_instances(monkeypatch)
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.time.time",
            lambda: (_ for _ in ()).throw(KeyboardInterrupt),
        )

        monitor.start_monitoring(str(tmp_path))
        monitor.start_monitoring(str(tmp_path), inline=True)

        assert [instance.kwargs["screen"] for instance in live_instances] == [
            True,
            False,
        ]
        assert all(
            instance.kwargs["refresh_per_second"] == 10
            for instance in live_instances
        )

    def test_sqlite_monitor_uses_full_screen_by_default_and_inline_when_requested(
        self, monkeypatch, tmp_path
    ):
        """Verify SQLite-based LiveMonitor uses full-screen by default and inline when requested.

        The test asserts that the Live context is created with `screen=True` for the
        default call and `screen=False` when invoked with `inline=True`.
        """
        workflow = {
            "workflow_id": "sqlite-workflow",
            "main_session": SimpleNamespace(
                session_id="sqlite-session",
                display_title="SQLite workflow",
                project_name="project",
                files=[],
                start_time=None,
            ),
            "all_sessions": [SimpleNamespace(session_id="sqlite-session")],
            "has_sub_agents": False,
            "display_title": "SQLite workflow",
            "project_name": "project",
            "session_count": 1,
            "sub_agent_count": 0,
        }
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "opencode.db"),
        )
        monkeypatch.setattr(
            monitor, "_get_sqlite_active_workflows", lambda *args, **kwargs: [workflow]
        )
        monkeypatch.setattr(
            monitor, "_generate_sqlite_workflow_dashboard", lambda *args: None
        )
        live_instances = self._record_live_instances(monkeypatch)
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.time.time",
            lambda: (_ for _ in ()).throw(KeyboardInterrupt),
        )

        monitor.start_sqlite_workflow_monitoring()
        monitor.start_sqlite_workflow_monitoring(inline=True)

        assert [instance.kwargs["screen"] for instance in live_instances] == [
            True,
            False,
        ]
        assert all(
            instance.kwargs["refresh_per_second"] == 10
            for instance in live_instances
        )


class TestMultiWorkflowTracking:
    def test_tracks_multiple_active_workflows(self, monkeypatch, tmp_path):
        active_workflow_a = {
            "workflow_id": "session-a",
            "main_session": MagicMock(session_id="session-a", end_time=None),
            "all_sessions": [MagicMock(session_id="session-a")],
        }
        active_workflow_b = {
            "workflow_id": "session-b",
            "main_session": MagicMock(session_id="session-b", end_time=None),
            "all_sessions": [MagicMock(session_id="session-b")],
        }

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            lambda db_path: [active_workflow_a, active_workflow_b],
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        assert monitor._get_tracked_workflow_ids() == {"session-a", "session-b"}

    def test_removes_ended_workflow_from_tracking(self, monkeypatch, tmp_path):
        ended_workflow = {
            "workflow_id": "session-ended",
            "main_session": MagicMock(session_id="session-ended", end_time=1000),
            "all_sessions": [MagicMock(session_id="session-ended")],
        }
        active_workflow = {
            "workflow_id": "session-active",
            "main_session": MagicMock(session_id="session-active", end_time=None),
            "all_sessions": [MagicMock(session_id="session-active")],
        }

        call_count = [0]

        def mock_get_workflows(db_path):
            call_count[0] += 1
            if call_count[0] == 1:
                return [ended_workflow, active_workflow]
            return [active_workflow]

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            mock_get_workflows,
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        assert monitor._get_tracked_workflow_ids() == {
            "session-ended",
            "session-active",
        }

        monitor._refresh_active_workflows(str(tmp_path / "test.db"))

        assert monitor._get_tracked_workflow_ids() == {"session-active"}

    def test_displays_most_recently_active_workflow(self, monkeypatch, tmp_path):
        now = 1700000000
        older_workflow = {
            "workflow_id": "session-old",
            "main_session": MagicMock(
                session_id="session-old",
                end_time=None,
                start_time=now - 3600,
            ),
            "all_sessions": [MagicMock(session_id="session-old")],
        }
        newer_workflow = {
            "workflow_id": "session-new",
            "main_session": MagicMock(
                session_id="session-new",
                end_time=None,
                start_time=now,
            ),
            "all_sessions": [MagicMock(session_id="session-new")],
        }

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            lambda db_path: [older_workflow, newer_workflow],
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        displayed = monitor._get_displayed_workflow()
        assert displayed["workflow_id"] == "session-new"

    def test_prev_tracked_reset_on_workflow_switch(self, monkeypatch, tmp_path):
        now = 1700000000
        workflow_a = {
            "workflow_id": "workflow-a",
            "main_session": MagicMock(
                session_id="workflow-a",
                end_time=None,
                start_time=now - 3600,
            ),
            "all_sessions": [
                MagicMock(session_id="session-a1"),
                MagicMock(session_id="session-a2"),
            ],
        }
        workflow_b = {
            "workflow_id": "workflow-b",
            "main_session": MagicMock(
                session_id="workflow-b",
                end_time=None,
                start_time=now,
            ),
            "all_sessions": [
                MagicMock(session_id="session-b1"),
            ],
        }

        call_count = [0]

        def mock_get_workflows(db_path):
            call_count[0] += 1
            if call_count[0] == 1:
                return [workflow_a]
            return [workflow_b]

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            mock_get_workflows,
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        assert monitor._get_displayed_workflow()["workflow_id"] == "workflow-a"
        assert monitor.prev_tracked == {"session-a1", "session-a2"}

        monitor._refresh_active_workflows(str(tmp_path / "test.db"))

        assert monitor._get_displayed_workflow()["workflow_id"] == "workflow-b"
        assert monitor.prev_tracked == set()

    def test_detects_new_sub_agent_during_poll(self, monkeypatch, tmp_path):
        now = 1700000000
        main_session = MagicMock(
            session_id="main-session",
            end_time=None,
            start_time=now,
        )

        workflow_initial = {
            "workflow_id": "workflow-with-subagents",
            "main_session": main_session,
            "all_sessions": [main_session],
            "sub_agents": [],
            "sub_agent_count": 0,
            "has_sub_agents": False,
        }

        sub_agent = MagicMock(
            session_id="sub-agent-1",
            end_time=None,
            start_time=now + 100,
        )

        workflow_with_subagent = {
            "workflow_id": "workflow-with-subagents",
            "main_session": main_session,
            "all_sessions": [main_session, sub_agent],
            "sub_agents": [sub_agent],
            "sub_agent_count": 1,
            "has_sub_agents": True,
        }

        call_count = [0]

        def mock_get_workflows(db_path):
            call_count[0] += 1
            if call_count[0] == 1:
                return [workflow_initial]
            return [workflow_with_subagent]

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            mock_get_workflows,
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        assert monitor.prev_tracked == {"main-session"}

        monitor._refresh_active_workflows(str(tmp_path / "test.db"))

        assert monitor.prev_tracked == {"main-session", "sub-agent-1"}

    def test_no_false_sub_agent_detection_on_workflow_switch(
        self, monkeypatch, tmp_path, caplog
    ):
        now = 1700000000
        workflow_a = {
            "workflow_id": "workflow-a",
            "main_session": MagicMock(
                session_id="session-a-main",
                end_time=None,
                start_time=now - 3600,
            ),
            "all_sessions": [
                MagicMock(session_id="session-a-main"),
                MagicMock(session_id="session-a-sub"),
            ],
        }
        workflow_b = {
            "workflow_id": "workflow-b",
            "main_session": MagicMock(
                session_id="session-b-main",
                end_time=None,
                start_time=now,
            ),
            "all_sessions": [
                MagicMock(session_id="session-b-main"),
                MagicMock(session_id="session-b-sub1"),
                MagicMock(session_id="session-b-sub2"),
            ],
        }

        call_count = [0]

        def mock_get_workflows(db_path):
            call_count[0] += 1
            if call_count[0] == 1:
                return [workflow_a]
            return [workflow_b]

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            mock_get_workflows,
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        assert monitor._get_displayed_workflow()["workflow_id"] == "workflow-a"
        assert monitor.prev_tracked == {
            "session-a-main",
            "session-a-sub",
        }, "prev_tracked initialized with workflow-a sessions"

        caplog.set_level(logging.INFO)
        monitor._refresh_active_workflows(str(tmp_path / "test.db"))

        assert monitor._get_displayed_workflow()["workflow_id"] == "workflow-b"
        assert monitor.prev_tracked == set(), (
            "prev_tracked should be empty after switching workflows; "
            "if it contained workflow-a sessions, they would interfere with tracking"
        )

        assert "New sub-agent detected" not in caplog.text, (
            "workflow-b sessions should NOT be falsely detected as new sub-agents "
            "even though prev_tracked had workflow-a sessions before the switch"
        )

        monitor._refresh_active_workflows(str(tmp_path / "test.db"))
        assert monitor.prev_tracked == {
            "session-b-main",
            "session-b-sub1",
            "session-b-sub2",
        }, "prev_tracked now tracks workflow-b sessions after stable refresh"


class TestParentActivitySelection:
    def test_selection_uses_parent_activity_only_not_sub_agent(
        self, monkeypatch, tmp_path
    ):
        from ocmonitor.models.session import TokenUsage
        from ocmonitor.models.session import InteractionFile
        from ocmonitor.models.session import TimeData

        now = 1700000000

        parent_file = MagicMock(spec=InteractionFile)
        parent_file.time_data = MagicMock(spec=TimeData)
        parent_file.time_data.created = (now - 100) * 1000
        parent_file.tokens = TokenUsage(input=100, output=50)

        parent_session = MagicMock(
            session_id="parent-a",
            end_time=None,
            start_time=now - 200,
            files=[parent_file],
        )

        sub_agent_file = MagicMock(spec=InteractionFile)
        sub_agent_file.time_data = MagicMock(spec=TimeData)
        sub_agent_file.time_data.created = now * 1000
        sub_agent_file.tokens = TokenUsage(input=200, output=100)

        sub_agent = MagicMock(
            session_id="sub-agent-a",
            end_time=None,
            start_time=now - 50,
            files=[sub_agent_file],
        )

        parent_b_file = MagicMock(spec=InteractionFile)
        parent_b_file.time_data = MagicMock(spec=TimeData)
        parent_b_file.time_data.created = (now - 50) * 1000
        parent_b_file.tokens = TokenUsage(input=50, output=25)

        parent_b = MagicMock(
            session_id="parent-b",
            end_time=None,
            start_time=now - 100,
            files=[parent_b_file],
        )

        workflow_a = {
            "workflow_id": "workflow-a",
            "main_session": parent_session,
            "all_sessions": [parent_session, sub_agent],
            "sub_agents": [sub_agent],
        }

        workflow_b = {
            "workflow_id": "workflow-b",
            "main_session": parent_b,
            "all_sessions": [parent_b],
            "sub_agents": [],
        }

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            lambda db_path: [workflow_a, workflow_b],
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        displayed = monitor._get_displayed_workflow()

        assert displayed["workflow_id"] == "workflow-b", (
            "Parent B should be displayed because its parent activity (now-50) "
            "is newer than Parent A's parent activity (now-100), "
            "even though Parent A's sub-agent has the newest activity (now)"
        )

    def test_parent_appears_when_dispatching_sub_agent(self, monkeypatch, tmp_path):
        from ocmonitor.models.session import TokenUsage
        from ocmonitor.models.session import InteractionFile
        from ocmonitor.models.session import TimeData

        now = 1700000000

        parent_a_file = MagicMock(spec=InteractionFile)
        parent_a_file.time_data = MagicMock(spec=TimeData)
        parent_a_file.time_data.created = now * 1000
        parent_a_file.tokens = TokenUsage(input=100, output=50)

        parent_a = MagicMock(
            session_id="parent-a",
            end_time=None,
            start_time=now - 100,
            files=[parent_a_file],
        )

        sub_agent = MagicMock(
            session_id="sub-agent-a",
            end_time=None,
            start_time=now + 50,
            files=[],
        )

        parent_b_file = MagicMock(spec=InteractionFile)
        parent_b_file.time_data = MagicMock(spec=TimeData)
        parent_b_file.time_data.created = (now - 50) * 1000
        parent_b_file.tokens = TokenUsage(input=50, output=25)

        parent_b = MagicMock(
            session_id="parent-b",
            end_time=None,
            start_time=now - 100,
            files=[parent_b_file],
        )

        workflow_a = {
            "workflow_id": "workflow-a",
            "main_session": parent_a,
            "all_sessions": [parent_a, sub_agent],
            "sub_agents": [sub_agent],
        }

        workflow_b = {
            "workflow_id": "workflow-b",
            "main_session": parent_b,
            "all_sessions": [parent_b],
            "sub_agents": [],
        }

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            lambda db_path: [workflow_a, workflow_b],
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        displayed = monitor._get_displayed_workflow()

        assert displayed["workflow_id"] == "workflow-a", (
            "Parent A should be displayed when it has new activity (dispatching sub-agent), "
            "even if sub-agent hasn't produced output yet"
        )
        assert len(displayed["sub_agents"]) == 1

    def test_workflow_shows_all_sub_agents_regardless_of_activity(
        self, monkeypatch, tmp_path
    ):
        from ocmonitor.models.session import TokenUsage
        from ocmonitor.models.session import InteractionFile
        from ocmonitor.models.session import TimeData

        now = 1700000000

        parent_file = MagicMock(spec=InteractionFile)
        parent_file.time_data = MagicMock(spec=TimeData)
        parent_file.time_data.created = now * 1000
        parent_file.tokens = TokenUsage(input=100, output=50)

        parent = MagicMock(
            session_id="parent",
            end_time=None,
            start_time=now - 100,
            files=[parent_file],
        )

        sub_agent_ended = MagicMock(
            session_id="sub-ended",
            end_time=now - 50,
            start_time=now - 80,
            files=[],
        )

        sub_agent_active = MagicMock(
            session_id="sub-active",
            end_time=None,
            start_time=now - 30,
            files=[],
        )

        workflow = {
            "workflow_id": "workflow-with-subs",
            "main_session": parent,
            "all_sessions": [parent, sub_agent_ended, sub_agent_active],
            "sub_agents": [sub_agent_ended, sub_agent_active],
        }

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            lambda db_path: [workflow],
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        displayed = monitor._get_displayed_workflow()

        assert displayed["workflow_id"] == "workflow-with-subs"
        assert len(displayed["sub_agents"]) == 2, (
            "Both ended and active sub-agents should be shown when parent is displayed"
        )


class TestOrphanSubAgentDetection:
    def test_single_orphan_group_creates_workflow(self, monkeypatch, tmp_path):
        from ocmonitor.utils.sqlite_utils import SQLiteProcessor

        orphan_workflow = {
            "workflow_id": "missing-parent-id",
            "main_session": MagicMock(
                session_id="orphan-sub-1", parent_id="missing-parent-id"
            ),
            "sub_agents": [
                MagicMock(session_id="orphan-sub-2", parent_id="missing-parent-id")
            ],
            "all_sessions": [
                MagicMock(session_id="orphan-sub-1"),
                MagicMock(session_id="orphan-sub-2"),
            ],
            "is_orphan": True,
        }

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            lambda db_path: [orphan_workflow],
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        displayed = monitor._get_displayed_workflow()

        assert displayed["workflow_id"] == "missing-parent-id"
        assert displayed["is_orphan"] is True
        assert len(displayed["sub_agents"]) == 1

    def test_multiple_orphan_groups_separate_workflows(self, monkeypatch, tmp_path):
        orphan_a = {
            "workflow_id": "parent-a",
            "main_session": MagicMock(session_id="sub-a1"),
            "sub_agents": [MagicMock(session_id="sub-a2")],
            "all_sessions": [MagicMock(), MagicMock()],
            "is_orphan": True,
        }
        orphan_b = {
            "workflow_id": "parent-b",
            "main_session": MagicMock(session_id="sub-b1"),
            "sub_agents": [],
            "all_sessions": [MagicMock()],
            "is_orphan": True,
        }

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            lambda db_path: [orphan_a, orphan_b],
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        tracked = monitor._get_tracked_workflow_ids()
        assert tracked == {"parent-a", "parent-b"}

    def test_mixed_normal_and_orphan_workflows(self, monkeypatch, tmp_path):
        from ocmonitor.models.session import TokenUsage
        from ocmonitor.models.session import InteractionFile
        from ocmonitor.models.session import TimeData

        now = 1700000000

        normal_file = MagicMock(spec=InteractionFile)
        normal_file.time_data = MagicMock(spec=TimeData)
        normal_file.time_data.created = now * 1000
        normal_file.tokens = TokenUsage(input=100, output=50)

        normal_workflow = {
            "workflow_id": "normal-parent",
            "main_session": MagicMock(session_id="normal-parent", files=[normal_file]),
            "sub_agents": [MagicMock(session_id="normal-sub")],
            "all_sessions": [MagicMock(), MagicMock()],
            "is_orphan": False,
        }

        orphan_workflow = {
            "workflow_id": "orphan-parent",
            "main_session": MagicMock(
                session_id="orphan-sub", files=[], parent_id="orphan-parent"
            ),
            "sub_agents": [],
            "all_sessions": [MagicMock()],
            "is_orphan": True,
        }

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: str(tmp_path / "test.db"),
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            lambda db_path: [normal_workflow, orphan_workflow],
        )

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        tracked = monitor._get_tracked_workflow_ids()
        assert "normal-parent" in tracked
        assert "orphan-parent" in tracked


class TestLiveMonitorValidation:
    def test_validate_monitoring_setup_uses_default_file_storage_when_path_not_provided(
        self, monkeypatch, tmp_path
    ):
        sessions_dir = tmp_path / "message"
        sessions_dir.mkdir()

        paths_config = PathsConfig(messages_dir=str(sessions_dir))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: None,
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.FileProcessor.find_session_directories",
            lambda _: [tmp_path / "session-1"],
        )

        result = monitor.validate_monitoring_setup()

        assert result["valid"] is True
        assert result["info"]["sqlite"]["available"] is False
        assert result["info"]["files"]["available"] is True
        assert result["info"]["files"]["path"] == str(sessions_dir)

    def test_validate_monitoring_setup_fails_when_default_file_storage_missing(
        self, monkeypatch, tmp_path
    ):
        missing_dir = tmp_path / "missing"

        paths_config = PathsConfig(messages_dir=str(missing_dir))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: None,
        )

        result = monitor.validate_monitoring_setup()

        assert result["valid"] is False
        assert (
            "No session data source found. Expected SQLite database or file storage."
            in result["issues"]
        )

    def test_validate_monitoring_setup_uses_explicit_base_path(
        self, monkeypatch, tmp_path
    ):
        explicit_path = tmp_path / "explicit-message"
        explicit_path.mkdir()

        paths_config = PathsConfig(messages_dir=str(tmp_path / "default-message"))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: None,
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.FileProcessor.find_session_directories",
            lambda _: [tmp_path / "session-1"],
        )

        result = monitor.validate_monitoring_setup(str(explicit_path))

        assert result["valid"] is True
        assert result["info"]["files"]["path"] == str(explicit_path)

    def test_validate_monitoring_setup_no_paths_config_and_no_base_path(
        self, monkeypatch
    ):
        monitor = LiveMonitor(pricing_data={})

        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: None,
        )

        result = monitor.validate_monitoring_setup()

        assert result["valid"] is False
        assert result["info"]["files"]["available"] is False


class TestLiveMonitorToolStatsSourceSelection:
    """Tests for tool stats source selection in live monitor."""

    def test_file_mode_tool_loading_does_not_fallback_to_sqlite(
        self, monkeypatch, tmp_path
    ):
        """Verify file-mode workflow doesn't pull SQLite tool stats even if SQLite is available."""
        sessions_dir = tmp_path / "message"
        sessions_dir.mkdir()

        paths_config = PathsConfig(messages_dir=str(sessions_dir))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        # Mock SQLite as available
        db_path = tmp_path / "opencode.db"
        db_path.touch()
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: db_path,
        )

        # Mock file processor to return sessions
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.FileProcessor.find_session_directories",
            lambda _: [tmp_path / "session-1"],
        )

        # Create a mock workflow with session IDs
        from unittest.mock import MagicMock

        mock_workflow = MagicMock()
        mock_workflow.all_sessions = [MagicMock(session_id="ses_file_1")]

        # Call with preferred_source="files"
        tool_stats = monitor._load_tool_stats_for_workflow(
            mock_workflow, preferred_source="files"
        )

        # Should return empty list for file mode, not SQLite data
        assert tool_stats == []

    def test_sqlite_mode_tool_loading_uses_sqlite(self, monkeypatch, tmp_path):
        """Verify SQLite-mode workflow queries SQLite for tool stats."""
        monitor = LiveMonitor(pricing_data={})

        # Mock SQLite as available
        db_path = tmp_path / "opencode.db"
        db_path.touch()
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: db_path,
        )

        # Mock the SQLite processor method to track calls
        from unittest.mock import MagicMock, patch

        mock_stats = [MagicMock(tool_name="bash", total_calls=5)]
        with patch(
            "ocmonitor.services.live_monitor.SQLiteProcessor.load_tool_usage_for_sessions",
            return_value=mock_stats,
        ) as mock_load:
            # Create a mock workflow with session IDs
            mock_workflow = MagicMock()
            mock_workflow.all_sessions = [MagicMock(session_id="ses_sqlite_1")]

            # Call with preferred_source="sqlite"
            tool_stats = monitor._load_tool_stats_for_workflow(
                mock_workflow, preferred_source="sqlite"
            )

            # Should have called SQLite processor
            mock_load.assert_called_once()
            assert tool_stats == mock_stats


class TestLiveMonitorSelection:
    def test_resolve_selected_sqlite_workflow_by_sub_agent_id(self):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)

        workflow_a = {
            "workflow_id": "workflow-a",
            "main_session": MagicMock(session_id="main-a"),
            "all_sessions": [MagicMock(session_id="main-a"), MagicMock(session_id="sub-a1")],
            "display_title": "Workflow A",
            "project_name": "proj-a",
            "session_count": 2,
            "sub_agent_count": 1,
        }
        workflow_b = {
            "workflow_id": "workflow-b",
            "main_session": MagicMock(session_id="main-b"),
            "all_sessions": [MagicMock(session_id="main-b")],
            "display_title": "Workflow B",
            "project_name": "proj-b",
            "session_count": 1,
            "sub_agent_count": 0,
        }

        resolved = monitor._resolve_selected_sqlite_workflow(
            [workflow_a, workflow_b], "sub-a1"
        )

        assert resolved is workflow_a

    def test_resolve_selected_file_workflow_by_sub_agent_id(self):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)

        workflow_a = SimpleNamespace(
            workflow_id="workflow-a",
            main_session=SimpleNamespace(session_id="main-a"),
            all_sessions=[
                SimpleNamespace(session_id="main-a"),
                SimpleNamespace(session_id="sub-a1"),
            ],
        )
        workflow_b = SimpleNamespace(
            workflow_id="workflow-b",
            main_session=SimpleNamespace(session_id="main-b"),
            all_sessions=[SimpleNamespace(session_id="main-b")],
        )

        resolved = monitor._resolve_selected_file_workflow(
            [workflow_a, workflow_b], "sub-a1"
        )

        assert resolved is workflow_a

    def test_handle_live_switch_command_next_previous_and_number(self):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)

        descriptors = [
            {"workflow_id": "wf-1"},
            {"workflow_id": "wf-2"},
            {"workflow_id": "wf-3"},
        ]

        new_id, should_quit = monitor._handle_live_switch_command(
            "n", descriptors, "wf-1"
        )
        assert should_quit is False
        assert new_id == "wf-2"

        new_id, should_quit = monitor._handle_live_switch_command(
            "p", descriptors, "wf-2"
        )
        assert should_quit is False
        assert new_id == "wf-1"

        new_id, should_quit = monitor._handle_live_switch_command(
            "3", descriptors, "wf-1"
        )
        assert should_quit is False
        assert new_id == "wf-3"

    def test_file_loader_disables_fallback_in_pinned_mode(self, monkeypatch, tmp_path):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)

        ended_workflow = SimpleNamespace(workflow_id="wf-ended", end_time=1)
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.FileProcessor.load_all_sessions",
            lambda base_path, limit=50: [SimpleNamespace(session_id="ses_1")],
        )
        monkeypatch.setattr(
            monitor.session_grouper,
            "group_sessions",
            lambda sessions: [ended_workflow],
        )

        result = monitor._get_file_active_workflows(
            str(tmp_path), allow_fallback=False
        )
        assert result == []

    def test_sqlite_loader_disables_fallback_in_pinned_mode(self, monkeypatch, tmp_path):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)

        db_path = tmp_path / "opencode.db"
        db_path.touch()
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: db_path,
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_all_active_workflows",
            lambda _: [],
        )
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.get_most_recent_workflow",
            lambda _: {"workflow_id": "wf-ended"},
        )

        result = monitor._get_sqlite_active_workflows(allow_fallback=False)
        assert result == []

    def test_handle_live_switch_command_show_does_not_switch(self):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)
        monitor._print_workflow_picker_table = MagicMock()

        new_id, should_quit = monitor._handle_live_switch_command(
            "s", [{"workflow_id": "wf-1"}], "wf-1"
        )

        assert should_quit is False
        assert new_id is None
        monitor._print_workflow_picker_table.assert_called_once()

    def test_handle_live_switch_command_invalid_number_does_not_switch(self):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)
        monitor.console.print = MagicMock()

        new_id, should_quit = monitor._handle_live_switch_command(
            "9", [{"workflow_id": "wf-1"}], "wf-1"
        )

        assert should_quit is False
        assert new_id is None
        monitor.console.print.assert_called()

    def test_handle_live_switch_command_unknown_does_not_switch(self):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)
        monitor.console.print = MagicMock()

        new_id, should_quit = monitor._handle_live_switch_command(
            "x", [{"workflow_id": "wf-1"}], "wf-1"
        )

        assert should_quit is False
        assert new_id is None
        monitor.console.print.assert_called()

    def test_apply_switch_command_selection_only_switches_on_new_id(self):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)

        selected, switched = monitor._apply_switch_command_selection(
            None, "wf-1", None
        )
        assert switched is False
        assert selected is None

        selected, switched = monitor._apply_switch_command_selection(
            None, "wf-1", "wf-1"
        )
        assert switched is False
        assert selected is None

        selected, switched = monitor._apply_switch_command_selection(
            None, "wf-1", "wf-2"
        )
        assert switched is True
        assert selected == "wf-2"

    def test_prompt_for_workflow_selection_accepts_number(self, monkeypatch):
        monitor = LiveMonitor(pricing_data={}, init_from_db=False)
        monkeypatch.setattr(
            monitor, "_print_workflow_picker_table", lambda descriptors, title: None
        )
        monkeypatch.setattr(monitor.console, "input", lambda _: "2")

        selected = monitor._prompt_for_workflow_selection(
            [
                {"workflow_id": "wf-1"},
                {"workflow_id": "wf-2"},
            ],
            "Select Workflow",
        )

        assert selected == "wf-2"


class TestLiveMonitorToolStatsByModelSourceSelection:
    def test_file_mode_tool_by_model_returns_empty(self, monkeypatch, tmp_path):
        """Verify file-mode workflow returns empty for tool by model loading."""
        sessions_dir = tmp_path / "message"
        sessions_dir.mkdir()

        paths_config = PathsConfig(messages_dir=str(sessions_dir))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        db_path = tmp_path / "opencode.db"
        db_path.touch()
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: db_path,
        )

        from unittest.mock import MagicMock

        mock_workflow = MagicMock()
        mock_workflow.all_sessions = [MagicMock(session_id="ses_file_1")]

        tool_stats = monitor._load_tool_stats_by_model_for_workflow(
            mock_workflow, preferred_source="files"
        )

        assert tool_stats == []

    def test_sqlite_mode_tool_by_model_calls_sqlite(self, monkeypatch, tmp_path):
        """Verify SQLite-mode workflow queries SQLite for tool by model stats."""
        monitor = LiveMonitor(pricing_data={})

        db_path = tmp_path / "opencode.db"
        db_path.touch()
        monkeypatch.setattr(
            "ocmonitor.services.live_monitor.SQLiteProcessor.find_database_path",
            lambda: db_path,
        )

        from unittest.mock import MagicMock, patch

        mock_stats = [MagicMock(model_name="claude-3-5-sonnet", tool_stats=[])]
        with patch(
            "ocmonitor.services.live_monitor.SQLiteProcessor.load_tool_usage_by_model_for_sessions",
            return_value=mock_stats,
        ) as mock_load:
            mock_workflow = MagicMock()
            mock_workflow.all_sessions = [MagicMock(session_id="ses_sqlite_1")]

            tool_stats = monitor._load_tool_stats_by_model_for_workflow(
                mock_workflow, preferred_source="sqlite"
            )

            mock_load.assert_called_once()
            assert tool_stats == mock_stats


class TestExecuteWorkflowSwitch:
    """Tests for the _execute_workflow_switch refactored method."""

    def test_execute_workflow_switch_no_switch_when_no_new_id(self, tmp_path):
        """Should return unchanged state when new_id is None."""
        from ocmonitor.services.live_monitor import LiveMonitor
        from ocmonitor.config import PathsConfig

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)
        monitor.prev_tracked = set()

        mock_workflow = MagicMock()
        mock_workflow.workflow_id = "wf-1"
        mock_workflow.all_sessions = [MagicMock(session_id="ses-1")]

        result_id, result_workflow, result_selected = monitor._execute_workflow_switch(
            new_id=None,
            selected_session_id=None,
            current_workflow_id="wf-1",
            current_workflow=mock_workflow,
            active_workflows=[mock_workflow],
            live=MagicMock(),
            descriptors=[],
            interactive_switch=False,
            refresh_interval=5,
        )

        assert result_id == "wf-1"
        assert result_workflow == mock_workflow
        assert result_selected is None
        assert monitor.prev_tracked == set()

    def test_execute_workflow_switch_no_switch_when_same_id(self, tmp_path):
        """Should return unchanged state when new_id matches current."""
        from ocmonitor.services.live_monitor import LiveMonitor
        from ocmonitor.config import PathsConfig

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        mock_workflow = MagicMock()
        mock_workflow.workflow_id = "wf-1"
        mock_workflow.all_sessions = [MagicMock(session_id="ses-1")]

        result_id, result_workflow, result_selected = monitor._execute_workflow_switch(
            new_id="wf-1",
            selected_session_id=None,
            current_workflow_id="wf-1",
            current_workflow=mock_workflow,
            active_workflows=[mock_workflow],
            live=MagicMock(),
            descriptors=[],
            interactive_switch=False,
            refresh_interval=5,
        )

        assert result_id == "wf-1"
        assert result_selected is None

    def test_execute_workflow_switch_switches_to_new_workflow(self, tmp_path):
        """Should update state and dashboard when switching to new workflow."""
        from ocmonitor.services.live_monitor import LiveMonitor
        from ocmonitor.config import PathsConfig

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)
        monitor.prev_tracked = {"old-session"}
        monitor._generate_workflow_dashboard = MagicMock(return_value="mock_dashboard")

        workflow_1 = MagicMock()
        workflow_1.workflow_id = "wf-1"
        workflow_1.all_sessions = [MagicMock(session_id="ses-1")]

        workflow_2 = MagicMock()
        workflow_2.workflow_id = "wf-2"
        workflow_2.all_sessions = [
            MagicMock(session_id="ses-2"),
            MagicMock(session_id="ses-2b"),
        ]

        live_mock = MagicMock()

        result_id, result_workflow, result_selected = monitor._execute_workflow_switch(
            new_id="wf-2",
            selected_session_id=None,
            current_workflow_id="wf-1",
            current_workflow=workflow_1,
            active_workflows=[workflow_1, workflow_2],
            live=live_mock,
            descriptors=[],
            interactive_switch=False,
            refresh_interval=5,
        )

        assert result_id == "wf-2"
        assert result_workflow == workflow_2
        assert result_selected == "wf-2"
        assert monitor.prev_tracked == {"ses-2", "ses-2b"}
        assert monitor._live_status_line is not None
        assert "Switched to workflow wf-2" in monitor._live_status_line
        live_mock.update.assert_called_once()


class TestHandleListCommand:
    """Tests for the _handle_list_command refactored method."""

    def test_handle_list_command_returns_unchanged_when_no_picker_selection(self, tmp_path):
        """Should return unchanged state when picker returns None."""
        from ocmonitor.services.live_monitor import LiveMonitor
        from ocmonitor.config import PathsConfig

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)
        monitor._pick_workflow_during_live = MagicMock(return_value=None)

        mock_workflow = MagicMock()
        mock_workflow.workflow_id = "wf-1"

        result_id, result_workflow, result_selected = monitor._handle_list_command(
            live=MagicMock(),
            descriptors=[{"workflow_id": "wf-1"}],
            selected_session_id="wf-1",
            current_workflow_id="wf-1",
            current_workflow=mock_workflow,
            active_workflows=[mock_workflow],
            interactive_switch=True,
            refresh_interval=5,
        )

        assert result_id == "wf-1"
        assert result_workflow == mock_workflow
        assert result_selected == "wf-1"

    def test_handle_list_command_switches_when_picker_selects(self, tmp_path):
        """Should switch workflow when picker returns a selection."""
        from ocmonitor.services.live_monitor import LiveMonitor
        from ocmonitor.config import PathsConfig

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        workflow_1 = MagicMock()
        workflow_1.workflow_id = "wf-1"
        workflow_1.all_sessions = [MagicMock(session_id="ses-1")]

        workflow_2 = MagicMock()
        workflow_2.workflow_id = "wf-2"
        workflow_2.all_sessions = [MagicMock(session_id="ses-2")]

        monitor._pick_workflow_during_live = MagicMock(return_value="wf-2")
        monitor._resolve_selected_file_workflow = MagicMock(return_value=workflow_2)
        monitor._generate_workflow_dashboard = MagicMock(return_value="mock_dashboard")

        live_mock = MagicMock()

        result_id, result_workflow, result_selected = monitor._handle_list_command(
            live=live_mock,
            descriptors=[{"workflow_id": "wf-1"}, {"workflow_id": "wf-2"}],
            selected_session_id="wf-1",
            current_workflow_id="wf-1",
            current_workflow=workflow_1,
            active_workflows=[workflow_1, workflow_2],
            interactive_switch=True,
            refresh_interval=5,
        )

        assert result_id == "wf-2"
        assert result_workflow == workflow_2
        assert result_selected == "wf-2"
        monitor._pick_workflow_during_live.assert_called_once()


class TestHandleNavigationCommand:
    """Tests for the _handle_navigation_command refactored method."""

    def test_handle_navigation_quit_command(self, tmp_path):
        """Should return should_quit=True when quit command received."""
        from ocmonitor.services.live_monitor import LiveMonitor
        from ocmonitor.config import PathsConfig

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        mock_workflow = MagicMock()
        mock_workflow.workflow_id = "wf-1"

        should_quit, workflow_id, workflow, selected = monitor._handle_navigation_command(
            command="q",
            descriptors=[{"workflow_id": "wf-1"}],
            selected_session_id="wf-1",
            current_workflow_id="wf-1",
            current_workflow=mock_workflow,
            active_workflows=[mock_workflow],
            live=MagicMock(),
            interactive_switch=True,
            refresh_interval=5,
        )

        assert should_quit is True
        assert workflow_id == "wf-1"
        assert workflow == mock_workflow
        assert selected == "wf-1"

    def test_handle_navigation_next_command_switches_workflow(self, tmp_path):
        """Should switch to next workflow on 'n' command."""
        from ocmonitor.services.live_monitor import LiveMonitor
        from ocmonitor.config import PathsConfig

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        workflow_1 = MagicMock()
        workflow_1.workflow_id = "wf-1"
        workflow_1.all_sessions = [MagicMock(session_id="ses-1")]

        workflow_2 = MagicMock()
        workflow_2.workflow_id = "wf-2"
        workflow_2.all_sessions = [MagicMock(session_id="ses-2")]

        monitor._resolve_selected_file_workflow = MagicMock(return_value=workflow_2)
        monitor._generate_workflow_dashboard = MagicMock(return_value="mock_dashboard")

        live_mock = MagicMock()

        should_quit, workflow_id, workflow, selected = monitor._handle_navigation_command(
            command="n",
            descriptors=[{"workflow_id": "wf-1"}, {"workflow_id": "wf-2"}],
            selected_session_id=None,
            current_workflow_id="wf-1",
            current_workflow=workflow_1,
            active_workflows=[workflow_1, workflow_2],
            live=live_mock,
            interactive_switch=True,
            refresh_interval=5,
        )

        assert should_quit is False
        assert workflow_id == "wf-2"
        assert workflow == workflow_2
        assert selected == "wf-2"
        live_mock.update.assert_called_once()

    def test_handle_navigation_prev_command_switches_workflow(self, tmp_path):
        """Should switch to previous workflow on 'p' command."""
        from ocmonitor.services.live_monitor import LiveMonitor
        from ocmonitor.config import PathsConfig

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        workflow_1 = MagicMock()
        workflow_1.workflow_id = "wf-1"
        workflow_1.all_sessions = [MagicMock(session_id="ses-1")]

        workflow_2 = MagicMock()
        workflow_2.workflow_id = "wf-2"
        workflow_2.all_sessions = [MagicMock(session_id="ses-2")]

        monitor._resolve_selected_file_workflow = MagicMock(return_value=workflow_1)
        monitor._generate_workflow_dashboard = MagicMock(return_value="mock_dashboard")

        live_mock = MagicMock()

        should_quit, workflow_id, workflow, selected = monitor._handle_navigation_command(
            command="p",
            descriptors=[{"workflow_id": "wf-1"}, {"workflow_id": "wf-2"}],
            selected_session_id=None,
            current_workflow_id="wf-2",
            current_workflow=workflow_2,
            active_workflows=[workflow_1, workflow_2],
            live=live_mock,
            interactive_switch=True,
            refresh_interval=5,
        )

        assert should_quit is False
        assert workflow_id == "wf-1"
        assert workflow == workflow_1
        assert selected == "wf-1"

    def test_handle_navigation_number_command_jumps_to_workflow(self, tmp_path):
        """Should jump to specific workflow on number command."""
        from ocmonitor.services.live_monitor import LiveMonitor
        from ocmonitor.config import PathsConfig

        paths_config = PathsConfig(messages_dir=str(tmp_path))
        monitor = LiveMonitor(pricing_data={}, paths_config=paths_config)

        workflow_1 = MagicMock()
        workflow_1.workflow_id = "wf-1"
        workflow_1.all_sessions = [MagicMock(session_id="ses-1")]

        workflow_2 = MagicMock()
        workflow_2.workflow_id = "wf-2"
        workflow_2.all_sessions = [MagicMock(session_id="ses-2")]

        workflow_3 = MagicMock()
        workflow_3.workflow_id = "wf-3"
        workflow_3.all_sessions = [MagicMock(session_id="ses-3")]

        monitor._resolve_selected_file_workflow = MagicMock(return_value=workflow_3)
        monitor._generate_workflow_dashboard = MagicMock(return_value="mock_dashboard")

        live_mock = MagicMock()

        should_quit, workflow_id, workflow, selected = monitor._handle_navigation_command(
            command="3",
            descriptors=[
                {"workflow_id": "wf-1"},
                {"workflow_id": "wf-2"},
                {"workflow_id": "wf-3"},
            ],
            selected_session_id=None,
            current_workflow_id="wf-1",
            current_workflow=workflow_1,
            active_workflows=[workflow_1, workflow_2, workflow_3],
            live=live_mock,
            interactive_switch=True,
            refresh_interval=5,
        )

        assert should_quit is False
        assert workflow_id == "wf-3"
        assert workflow == workflow_3
        assert selected == "wf-3"


class TestLiveMonitorProviderAwareRegressions:
    """Regression tests for provider-aware pricing lookups in live monitor."""

    def test_session_context_usage_uses_provider_aware_context_window(self, tmp_path):
        """Provider/model pricing should be used instead of default context window."""
        from decimal import Decimal
        from ocmonitor.config import ModelPricing
        from ocmonitor.models.session import InteractionFile, SessionData, TokenUsage

        pricing_data = {
            "github-copilot/claude-sonnet-4.5": ModelPricing(
                input=Decimal("1.0"),
                output=Decimal("2.0"),
                cacheWrite=Decimal("0.0"),
                cacheRead=Decimal("0.0"),
                contextWindow=100000,
                sessionQuota=Decimal("5.0"),
            )
        }

        monitor = LiveMonitor(pricing_data=pricing_data, paths_config=PathsConfig(messages_dir=str(tmp_path)))

        inter_file = tmp_path / "inter_0001.json"
        inter_file.write_text("{}")
        interaction = InteractionFile(
            file_path=inter_file,
            session_id="ses_test",
            model_id="claude-sonnet-4.5",
            provider_id="github-copilot",
            tokens=TokenUsage(input=1000, output=100, cache_read=200, cache_write=300),
            raw_data={},
        )
        session = SessionData(
            session_id="ses_test",
            session_path=tmp_path / "ses_test",
            files=[interaction],
        )

        result = monitor._get_session_context_usage(session)

        assert "claude-sonnet-4.5" in result
        assert result["claude-sonnet-4.5"]["context_window"] == 100000
