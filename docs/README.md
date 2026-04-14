# Linkora - AI Voice Assistant Platform Documentation

Welcome to the Linkora platform documentation. This directory contains comprehensive guides for all components of the system.

## 📚 Documentation Structure

### Core Documentation
- [**Getting Started**](getting-started.md) - Quick start guide for new developers
- [**Architecture Overview**](architecture.md) - System architecture and design decisions

### Component Documentation
- [**ConnectX (Mobile App)**](connectx.md) - Flutter mobile application documentation
- [**AI-Assistant (Backend)**](ai-assistant.md) - Python WebRTC server documentation
- [**Weaviate (Database)**](weaviate.md) - Vector database setup and configuration

### Infrastructure Documentation
- [**Deployment**](deployment.md) - Cloud Run + Compute Engine setup

### Legal
- [**Privacy Policy**](legal/privacy-policy.html)
- [**Terms of Use**](legal/terms-of-use.html)
- [**Legal Notice**](legal/legal-notice.html)
- [**Disclaimer**](legal/disclaimer.html)

## 🎯 Quick Links

### For New Developers
1. Start with [Getting Started](getting-started.md)
2. Review [Architecture Overview](architecture.md)

### For Mobile Developers
- [ConnectX Documentation](connectx.md)

### For Backend Developers
- [AI-Assistant Documentation](ai-assistant.md)
- [Weaviate Documentation](weaviate.md)

### For DevOps
- [Deployment](deployment.md)

## 🔗 Repository Structure

```
Linkora/
├── docs/                 # 📖 This documentation directory
├── connectx/             # 📱 Flutter mobile application
├── ai-assistant/         # 🤖 Python WebRTC server
├── weaviate/             # 🗄️ Weaviate docker-compose + VM startup script
└── .github/workflows/    # 🔄 CI/CD pipelines
```

## 📝 Document Conventions

All documentation follows these conventions:
- **Headers**: Use emoji for section identification
- **Code blocks**: Include language identifiers for syntax highlighting
- **Links**: Use relative paths within documentation
- **Examples**: Provide working, copy-pasteable examples
- **Updates**: Keep documentation in sync with code changes