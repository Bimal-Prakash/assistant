# Contributing to Jarvis Assistant

Thank you for your interest in contributing! Here's how you can help.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```powershell
   git clone https://github.com/Bimal-Prakash/assistant.git
   cd assistant
   ```

3. **Create a virtual environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. **Install dependencies in development mode**:
   ```powershell
   pip install -r requirements.txt
   ```

## Development Workflow

1. **Create a feature branch**:
   ```powershell
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and test thoroughly
3. **Commit with clear messages**:
   ```powershell
   git commit -m "Add feature: description of changes"
   ```

4. **Push to your fork**:
   ```powershell
   git push origin feature/your-feature-name
   ```

5. **Submit a Pull Request** on GitHub

## Code Guidelines

- Follow **PEP 8** Python style guide
- Add **docstrings** to functions and classes
- Include **type hints** where possible
- Write **descriptive commit messages**
- Test your changes before submitting

## Areas for Contribution

### Bug Fixes
- Report issues in the GitHub Issues
- Check existing issues before submitting
- Include reproduction steps and logs

### Features
- Voice command improvements
- New system integrations
- Performance optimizations
- Documentation enhancements

### Testing
- Test on different Windows versions
- Test with different STT engines
- Report compatibility issues

## Code Style

```python
# Good: clear, typed, documented
def handle_command(text: str, client: str) -> Dict[str, Any]:
    """
    Process a voice command and return the action to execute.
    
    Args:
        text: The recognized command text
        client: The client identifier (pc or android)
        
    Returns:
        Dictionary containing action details
    """
    # Implementation
    pass
```

## Testing

Before submitting:
- Test basic functionality
- Test edge cases
- Verify no errors in logs
- Check on Windows 10/11

## Documentation

- Update README.md for user-facing changes
- Add comments for complex logic
- Document configuration options
- Update this file if adding new contribution types

## Data Privacy

⚠️ **Important**: Never commit:
- `jarvis_memory.sqlite3` (personal memory database)
- `.env` files with credentials
- `contacts.json` with personal phone numbers
- Any user-specific configuration

Use `.gitignore` to exclude these files.

## Questions?

- Check existing GitHub Issues
- Open a new issue for questions
- Review the README and documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for helping improve Jarvis Assistant! 🎤
