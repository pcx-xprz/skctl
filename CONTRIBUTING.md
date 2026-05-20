# Contributing to Sky Auto CR Bot

Thank you for considering contributing to this project! 🌟

## Code of Conduct

Be respectful and constructive in all interactions.

## How to Contribute

### Reporting Bugs

Found a bug? Please create an issue with:
- **Title**: Clear, descriptive title
- **Description**: What happened vs what you expected
- **Steps to reproduce**
- **Environment**: OS, Python version, game version
- **Screenshots** (if applicable)
- **Logs** (from `logs/bot.log`)

### Suggesting Features

Have an idea? Create an issue with:
- **Feature description**
- **Use case**: Why is this useful?
- **Possible implementation** (optional)

### Pull Requests

1. **Fork the repository**
2. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
4. **Test thoroughly**
5. **Commit with clear messages**:
   ```bash
   git commit -m "feat: add new candle detection algorithm"
   ```
6. **Push to your fork**
7. **Create Pull Request**

## Development Setup

```bash
# Clone
git clone https://github.com/pcx-xprz/skctl.git
cd skctl

# Virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dev dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # if available

# Run tests
pytest tests/

# Run linting
flake8 src/
black src/
```

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for all functions
- Keep functions small and focused
- Add comments for complex logic

### Example:

```python
def detect_candles(
    self, 
    image: np.ndarray, 
    debug: bool = False
) -> List[CandleLocation]:
    """
    Detect candles in image using HSV color filtering.
    
    Args:
        image: Input BGR image from game screen
        debug: If True, save intermediate processing images
        
    Returns:
        List of detected candle locations sorted by distance
        
    Raises:
        ValueError: If image is empty or invalid
    """
    # Implementation
    pass
```

## Testing

All contributions should include tests:

```python
def test_candle_detection():
    """Test candle detector with sample image"""
    detector = CandleDetector()
    image = cv2.imread("tests/fixtures/sample_game_screen.png")
    
    candles = detector.detect_candles(image)
    
    assert len(candles) > 0
    assert candles[0].confidence > 0.5
```

## Documentation

- Update README.md if changing core functionality
- Update USAGE.md for new features
- Add docstrings to new functions
- Comment complex algorithms

## Areas for Contribution

### High Priority
- [ ] Improved candle detection algorithm
- [ ] Better pathfinding (A* implementation)
- [ ] Android ADB support
- [ ] Multi-realm navigation
- [ ] Quest automation

### Medium Priority
- [ ] GUI interface (alternative to Telegram)
- [ ] Machine learning candle recognition
- [ ] Auto-updater
- [ ] Configuration wizard
- [ ] Better error recovery

### Low Priority
- [ ] Statistics dashboard
- [ ] Multiple account management
- [ ] Scheduling system
- [ ] Discord bot alternative
- [ ] Web interface

## Project Structure

```
skctl/
├── src/
│   ├── auth/          # OAuth & authentication
│   ├── cv/            # Computer vision & detection
│   ├── bot/           # Telegram bot interface
│   ├── automation/    # Game input automation
│   └── utils/         # Utilities & helpers
├── tests/             # Unit tests
├── logs/              # Log files
├── data/              # User data & tokens
├── config/            # Configuration files
├── docs/              # Additional documentation
└── main.py            # Entry point
```

## Commit Message Convention

Use conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

Examples:
```
feat: add wax cluster detection
fix: character stuck recovery
docs: update installation guide
refactor: improve candle detector performance
```

## Review Process

1. Maintainer reviews PR
2. Feedback/changes requested (if needed)
3. You make updates
4. Approval & merge

## Questions?

- Open an issue with `question` label
- Join our community chat
- Contact maintainers

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing! 🙏✨
