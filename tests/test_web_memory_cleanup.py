import time
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from src.agent.web.app import TaskState, cleanup_expired_tasks

@pytest.fixture
def mock_app():
    """Фиктивное приложение для тестирования очистки."""
    app = FastAPI()
    app.state.tasks = {}
    return app

def test_cleanup_finished_tasks(mock_app):
    """Проверяет, что завершенные задачи удаляются через 5 минут."""
    # Завершенная задача, завершенная 6 минут назад (должна удалиться)
    st1 = TaskState()
    st1.events.append(None)
    st1.mark_finished()
    st1.finished_at = time.time() - 360  # 6 минут назад
    
    # Завершенная задача, завершенная 1 минуту назад (не должна удалиться)
    st2 = TaskState()
    st2.events.append(None)
    st2.mark_finished()
    st2.finished_at = time.time() - 60
    
    mock_app.state.tasks = {"task1": st1, "task2": st2}
    
    deleted = cleanup_expired_tasks(mock_app, time.time())
    
    assert deleted == 1
    assert "task1" not in mock_app.state.tasks
    assert "task2" in mock_app.state.tasks

def test_cleanup_stuck_tasks(mock_app):
    """Проверяет, что брошенные незавершенные задачи удаляются через 2 часа."""
    # Брошенная задача, созданная 3 часа назад (должна удалиться)
    st1 = TaskState()
    st1.created_at = time.time() - 10800  # 3 часа назад
    
    # Свежая незавершенная задача (не должна удалиться)
    st2 = TaskState()
    
    mock_app.state.tasks = {"task1": st1, "task2": st2}
    
    deleted = cleanup_expired_tasks(mock_app, time.time())
    
    assert deleted == 1
    assert "task1" not in mock_app.state.tasks
    assert "task2" in mock_app.state.tasks

def test_cleanup_mixed_tasks(mock_app):
    """Проверяет смешанный сценарий: завершенные и брошенные задачи."""
    now = time.time()
    
    st_finished = TaskState()
    st_finished.events.append(None)
    st_finished.mark_finished()
    st_finished.finished_at = now - 400  # > 5 минут
    
    st_stuck = TaskState()
    st_stuck.created_at = now - 8000  # > 2 часов
    
    st_fresh = TaskState()
    
    mock_app.state.tasks = {
        "finished": st_finished,
        "stuck": st_stuck,
        "fresh": st_fresh,
    }
    
    deleted = cleanup_expired_tasks(mock_app, now)
    
    assert deleted == 2
    assert "finished" not in mock_app.state.tasks
    assert "stuck" not in mock_app.state.tasks
    assert "fresh" in mock_app.state.tasks

def test_task_state_is_finished():
    """Проверяет логику is_finished и mark_finished."""
    st = TaskState()
    assert not st.is_finished()
    assert st.finished_at is None
    
    st.events.append("some_event")
    assert not st.is_finished()
    
    st.events.append(None)
    assert st.is_finished()
    assert st.finished_at is None  # mark_finished еще не вызван
    
    st.mark_finished()
    assert st.finished_at is not None
    
    # Повторный вызов не должен менять время
    initial_time = st.finished_at
    time.sleep(0.01)
    st.mark_finished()
    assert st.finished_at == initial_time