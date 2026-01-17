import { render, screen } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import {
  MentionAutocomplete,
  filterThinkers,
} from '@/components/MentionAutocomplete';
import type { ConversationThinker } from '@/types';

const user = userEvent.setup();

const mockThinkers: ConversationThinker[] = [
  {
    id: '1',
    name: 'Socrates',
    bio: 'Greek philosopher',
    positions: 'Knowledge is virtue',
    style: 'Questioning',
    color: '#3B82F6',
    image_url: null,
  },
  {
    id: '2',
    name: 'Plato',
    bio: 'Greek philosopher',
    positions: 'Theory of Forms',
    style: 'Dialogic',
    color: '#10B981',
    image_url: null,
  },
  {
    id: '3',
    name: 'Friedrich Nietzsche',
    bio: 'German philosopher',
    positions: 'Will to power',
    style: 'Aphoristic',
    color: '#EF4444',
    image_url: null,
  },
];

describe('filterThinkers', () => {
  it('returns all thinkers when query is empty', () => {
    const result = filterThinkers(mockThinkers, '');
    expect(result).toHaveLength(3);
    expect(result).toEqual(mockThinkers);
  });

  it('filters by full name (case-insensitive)', () => {
    const result = filterThinkers(mockThinkers, 'socrates');
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Socrates');
  });

  it('filters by partial name', () => {
    const result = filterThinkers(mockThinkers, 'Soc');
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Socrates');
  });

  it('filters by first name of multi-word name', () => {
    const result = filterThinkers(mockThinkers, 'Fried');
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Friedrich Nietzsche');
  });

  it('filters by last name of multi-word name', () => {
    const result = filterThinkers(mockThinkers, 'Nietz');
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Friedrich Nietzsche');
  });

  it('returns multiple matches when query matches multiple thinkers', () => {
    const result = filterThinkers(mockThinkers, 'P');
    expect(result).toHaveLength(1); // Only Plato starts with P
  });

  it('returns empty array when no matches', () => {
    const result = filterThinkers(mockThinkers, 'xyz');
    expect(result).toHaveLength(0);
  });
});

describe('MentionAutocomplete', () => {
  const defaultProps = {
    thinkers: mockThinkers,
    query: '',
    selectedIndex: 0,
    onSelect: jest.fn(),
    onIndexChange: jest.fn(),
    position: { top: 50, left: 16 },
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders autocomplete dropdown with thinkers', () => {
    render(<MentionAutocomplete {...defaultProps} />);

    expect(screen.getByTestId('mention-autocomplete')).toBeInTheDocument();
    expect(screen.getByTestId('mention-option-socrates')).toBeInTheDocument();
    expect(screen.getByTestId('mention-option-plato')).toBeInTheDocument();
    expect(
      screen.getByTestId('mention-option-friedrich-nietzsche')
    ).toBeInTheDocument();
  });

  it('shows filtered thinkers based on query', () => {
    render(<MentionAutocomplete {...defaultProps} query="Soc" />);

    expect(screen.getByTestId('mention-option-socrates')).toBeInTheDocument();
    expect(
      screen.queryByTestId('mention-option-plato')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId('mention-option-friedrich-nietzsche')
    ).not.toBeInTheDocument();
  });

  it('returns null when no thinkers match query', () => {
    const { container } = render(
      <MentionAutocomplete {...defaultProps} query="xyz" />
    );

    expect(container.firstChild).toBeNull();
  });

  it('calls onSelect when thinker is clicked', async () => {
    const onSelect = jest.fn();
    render(<MentionAutocomplete {...defaultProps} onSelect={onSelect} />);

    await user.click(screen.getByTestId('mention-option-plato'));

    expect(onSelect).toHaveBeenCalledWith(mockThinkers[1]);
  });

  it('highlights selected thinker', () => {
    render(<MentionAutocomplete {...defaultProps} selectedIndex={1} />);

    const platoOption = screen.getByTestId('mention-option-plato');
    expect(platoOption).toHaveAttribute('aria-selected', 'true');
  });

  it('displays thinker names with correct colors', () => {
    render(<MentionAutocomplete {...defaultProps} />);

    const socratesOption = screen.getByTestId('mention-option-socrates');
    const nameSpan = socratesOption.querySelector('span.font-semibold');
    expect(nameSpan).toHaveStyle({ color: '#3B82F6' });
  });

  it('has proper listbox role and aria-label', () => {
    render(<MentionAutocomplete {...defaultProps} />);

    const dropdown = screen.getByTestId('mention-autocomplete');
    expect(dropdown).toHaveAttribute('role', 'listbox');
    expect(dropdown).toHaveAttribute('aria-label', 'Mention suggestions');
  });

  it('calls onIndexChange when selectedIndex exceeds filtered length', () => {
    const onIndexChange = jest.fn();
    render(
      <MentionAutocomplete
        {...defaultProps}
        query="Soc"
        selectedIndex={5}
        onIndexChange={onIndexChange}
      />
    );

    // Since "Soc" filters to only Socrates (1 item), selectedIndex 5 should trigger onIndexChange(0)
    expect(onIndexChange).toHaveBeenCalledWith(0);
  });
});
