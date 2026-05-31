# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Jarvis Assistant, please report it responsibly.

### How to Report

1. **Do NOT open a public GitHub issue** for security vulnerabilities
2. **Email the maintainers** with details of the vulnerability
3. Include:
   - Description of the vulnerability
   - Steps to reproduce (if applicable)
   - Potential impact
   - Suggested fix (if you have one)

### Response Timeline

- **Acknowledgment**: Within 48 hours of report
- **Investigation**: 3-5 business days
- **Resolution**: Varies based on complexity
- **Public disclosure**: After a fix is released or 90 days, whichever is sooner

## Security Considerations

### Data Privacy

- **Memory database** (`jarvis_memory.sqlite3`) stores personal information
- Store database in secure, user-accessible-only locations
- Use `.gitignore` to prevent accidentally committing personal data
- Delete database before sharing or publishing code

### Credentials

- Never hardcode API keys or passwords
- Use `.env` files (excluded from git) for sensitive configuration
- Use environment variables for production deployment
- Rotate credentials regularly

### Network Security

- Backend runs on `localhost:8000` by default (not exposed)
- For remote access, use VPN or SSH tunneling
- Don't expose the Ollama API port to untrusted networks
- Consider using HTTPS proxies for remote deployments

### Input Validation

- Voice commands are processed through Ollama
- System commands are rate-limited and filtered
- User-supplied data is sanitized before execution

## Known Issues

None currently reported. Please report any security issues using the process above.

## Dependencies

Keep dependencies updated:
```powershell
pip install --upgrade -r requirements.txt
```

Monitor for security updates in:
- Ollama
- FastAPI
- Requests
- Other Python packages

## Recommendations

### For Users

- Run on trusted networks only
- Keep Windows and Python updated
- Review command output before confirming system changes
- Use strong passwords in contacts if stored

### For Developers

- Review code before merging PRs
- Don't expose backend to public internet
- Test with latest dependency versions
- Follow secure coding practices

## Contact

For security inquiries, please reach out to the maintainers privately.

---

Thank you for helping keep Jarvis Assistant secure!
