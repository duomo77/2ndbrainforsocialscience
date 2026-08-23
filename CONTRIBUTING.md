# Contributing to ROS

Thank you for your interest in contributing! This document outlines guidelines and processes.

## 🎯 Development Guidelines

### Code Style

#### Python
```python
# Follow PEP 8 with these specific rules:
- Line length: 100 chars max
- Indentation: 4 spaces
- Imports: Grouped and sorted (standard lib, third-party, local)
- Type hints: Required for all function signatures
- Docstrings: Google style for public functions/classes
```

Example:
```python
from typing import Dict, List, Optional

import requests
from core.base_provider import BaseLLMProvider


class ExampleClass(BaseLLMProvider):
    """Brief description of class.

    Longer description if needed.

    Args:
        param1: Description of parameter
    """

    def __init__(self, param1: str, param2: int = 10) -> None:
        self.param1 = param1
        self.param2 = param2

    def process(self, data: Dict[str, Any]) -> Optional[bool]:
        """Process input data.

        Args:
            data: Input dictionary to process

        Returns:
            True if successful, False otherwise
        """
        if not data:
            return False
        return True
```

#### Frontend (Tkinter)
```python
# Organize widgets logically
# Use meaningful variable names
# Separate creation logic from event handlers
# Comment complex layout calculations

def create_widgets(self):
    """Create all UI widgets."""
    # Header section
    header_frame = ttk.Frame(self.root)
    
    # Input section
    input_frame = self._create_input_section()
    
    # Results section  
    results_frame = self._create_results_section()
```

### Git Workflow

1. **Fork and clone** repository
2. **Create feature branch**: `git checkout -b feature/description`
3. **Make changes** in focused commits
4. **Write tests** for new functionality
5. **Run all tests**: `pytest -v`
6. **Update documentation** if applicable
7. **Submit PR** with clear description

### Commit Messages

Use conventional commits format:

```
type(scope): subject

body (optional)

footer (optional)
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, no logic change
- `refactor`: Code restructuring
- `test`: Test additions/changes
- `chore`: Build/config changes

Examples:
```
feat(qwen): Add streaming support for Qwen provider

Implement generator-based streaming for large responses.
Includes rate limiting and automatic retry logic.

Closes #123
```

```
refactor(ui): Extract graph visualization into separate module

Move graph rendering code from main window to dedicated class
for better testability and maintainability.
```

## 🧪 Testing Requirements

### Writing Tests

All new features require tests:

```python
"""Tests for module functionality"""
import pytest
from unittest.mock import Mock, patch


class TestNewFeature:
    """Test suite for new feature"""
    
    @pytest.fixture
    def setup(self):
        """Setup fixture"""
        return {"key": "value"}
    
    def test_happy_path(self, setup):
        """Test normal operation"""
        result = function(setup["key"])
        assert result == expected
    
    def test_edge_case(self):
        """Test boundary conditions"""
        with pytest.raises(ValueError):
            function(None)
    
    @patch('external.api.call')
    def test_external_dependency(self, mock_call):
        """Test with mocked external services"""
        mock_call.return_value = success_response
        result = function_with_api()
        mock_call.assert_called_once()
```

### Running Tests

```bash
# Full test suite
pytest -v

# Specific test file
pytest test_new_feature.py -v

# With coverage report
pytest --cov=core --cov-report=html

# Failed tests only
pytest --lf

# Watch mode during development
pytest --watch
```

### Coverage Thresholds

| Component | Minimum Coverage |
|-----------|-----------------|
| Core modules | 90% |
| UI components | 75% |
| Provider integrations | 95% |
| Utilities | 85% |

## 📝 Documentation Standards

### Module Docstrings

```python
"""Module description.

Single paragraph explaining what this module does, key classes/functions,
and any important usage notes or caveats.

Example:
    from module import KeyClass
    
    obj = KeyClass(param1, param2)
    result = obj.method()

Attributes:
    MODULE_CONSTANT: Description

See Also:
    RelatedModule, AnotherRelatedModule
"""
```

### API Documentation

Document all public APIs:

```python
def public_function(param1: str, param2: int = 10) -> bool:
    """Function description.
    
    Detailed explanation of behavior, side effects, etc.
    
    Args:
        param1: Required parameter description
        param2: Optional parameter with default
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param1 is empty
        TypeError: When param2 is not an integer
        
    Example:
        >>> result = public_function("hello", 20)
        >>> print(result)
        True
    """
    pass
```

### README Updates

If user-facing changes:
- Update installation instructions if dependencies changed
- Add usage examples for new features
- Document breaking changes clearly
- Include screenshots for UI changes

## 🐛 Bug Reports

### Creating a Bug Report

Template for issues:

```markdown
**Describe the bug**
Clear, concise description

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
What should happen

**Screenshots**
If applicable

**Environment:**
- OS: [e.g. macOS 14.0]
- Python version: [e.g. 3.9.7]
- ROS version: [e.g. v1.2.3]

**Additional context**
Any other relevant information
```

## 🚀 Pull Request Process

### Before Submitting

1. ✅ All tests pass locally
2. ✅ Code follows style guidelines
3. ✅ Documentation updated
4. ✅ No linting errors (`flake8`, `black --check`)
5. ✅ Changelog entry added if user-facing

### PR Template

```markdown
## Description
Brief summary of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Added unit tests
- [ ] Ran full test suite
- [ ] Tested manually

## Screenshots (if UI change)
Before/after images

## Checklist
- [ ] Code follows project conventions
- [ ] Self-review completed
- [ ] Comments added for complex sections
- [ ] Docs updated
- [ ] Changelog updated

## Related Issues
Closes #XXX
```

## 🔍 Code Review

### What Reviewers Look For

1. **Correctness**: Does it work as intended?
2. **Clarity**: Is the code readable and well-named?
3. **Testing**: Are edge cases covered?
4. **Performance**: Any inefficiencies?
5. **Security**: No vulnerabilities introduced?
6. **Consistency**: Matches existing patterns?

### Response to Feedback

- Address all comments or explain disagreements politely
- Make incremental commits for review feedback
- Ping reviewers when ready for re-review
- Don't force-push after review starts

## 📋 Development Setup

### Local Environment

```bash
# Clone repository
git clone https://github.com/your-org/ros.git
cd ros

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Pre-commit hooks (optional)
pre-commit install
```

### Useful Commands

```bash
# Format code
black .
isort .

# Lint
flake8 core/ frontend/
mypy core/

# Run tests
pytest -v

# Build distribution
python setup.py sdist bdist_wheel
```

## 🤝 Community Guidelines

- Be respectful and inclusive
- Give constructive feedback
- Help others when possible
- Credit original authors
- Report security issues privately

## 📞 Getting Help

- **Questions**: Open GitHub Discussion
- **Bugs**: Create Issue with template
- **Features**: RFC in Discussions first
- **Urgent**: Contact maintainers directly

---

Thanks for contributing to ROS! 🎉
