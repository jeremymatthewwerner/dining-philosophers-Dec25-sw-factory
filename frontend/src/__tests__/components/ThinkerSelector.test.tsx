import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThinkerSelector } from '@/components/ThinkerSelector';
import type { ThinkerProfile, ThinkerSuggestion } from '@/types';

const createSuggestion = (name: string): ThinkerSuggestion => ({
  name,
  reason: `${name} would be great for this discussion`,
  profile: {
    name,
    bio: `Bio of ${name}`,
    positions: 'Some positions',
    style: 'Some style',
  },
});

const createSelectedThinker = (name: string) => ({
  name,
  profile: {
    name,
    bio: `Bio of ${name}`,
    positions: 'Some positions',
    style: 'Some style',
  },
});

describe('ThinkerSelector', () => {
  const defaultProps = {
    suggestions: [] as ThinkerSuggestion[],
    selectedThinkers: [] as { name: string; profile: ThinkerProfile }[],
    onSelect: jest.fn(),
    onRemove: jest.fn(),
    onValidateCustom: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders empty state', () => {
    render(<ThinkerSelector {...defaultProps} />);
    expect(screen.getByTestId('thinker-selector')).toBeInTheDocument();
  });

  it('renders suggestions', () => {
    const suggestions = [
      createSuggestion('Socrates'),
      createSuggestion('Plato'),
    ];
    render(<ThinkerSelector {...defaultProps} suggestions={suggestions} />);

    expect(screen.getByText('Socrates')).toBeInTheDocument();
    expect(screen.getByText('Plato')).toBeInTheDocument();
  });

  it('calls onSelect when accept button is clicked', () => {
    const onSelect = jest.fn();
    const suggestions = [createSuggestion('Socrates')];
    render(
      <ThinkerSelector
        {...defaultProps}
        suggestions={suggestions}
        onSelect={onSelect}
      />
    );

    fireEvent.click(screen.getByTestId('accept-suggestion'));
    expect(onSelect).toHaveBeenCalledWith({
      name: 'Socrates',
      profile: suggestions[0].profile,
    });
  });

  it('calls onRefreshSuggestion when refresh button is clicked', async () => {
    const onRefreshSuggestion = jest.fn().mockResolvedValue(undefined);
    const suggestions = [createSuggestion('Socrates')];
    render(
      <ThinkerSelector
        {...defaultProps}
        suggestions={suggestions}
        onRefreshSuggestion={onRefreshSuggestion}
      />
    );

    fireEvent.click(screen.getByTestId('refresh-suggestion'));
    await waitFor(() => {
      expect(onRefreshSuggestion).toHaveBeenCalledWith('Socrates');
    });
  });

  it('renders selected thinkers', () => {
    const selectedThinkers = [createSelectedThinker('Socrates')];
    render(
      <ThinkerSelector {...defaultProps} selectedThinkers={selectedThinkers} />
    );

    expect(screen.getByTestId('selected-thinker')).toBeInTheDocument();
    expect(screen.getByText('Socrates')).toBeInTheDocument();
  });

  it('calls onRemove when selected thinker is removed', () => {
    const onRemove = jest.fn();
    const selectedThinkers = [createSelectedThinker('Socrates')];
    render(
      <ThinkerSelector
        {...defaultProps}
        selectedThinkers={selectedThinkers}
        onRemove={onRemove}
      />
    );

    fireEvent.click(screen.getByLabelText('Remove Socrates'));
    expect(onRemove).toHaveBeenCalledWith('Socrates');
  });

  it('filters out already selected thinkers from suggestions', () => {
    const suggestions = [
      createSuggestion('Socrates'),
      createSuggestion('Plato'),
    ];
    const selectedThinkers = [createSelectedThinker('Socrates')];
    render(
      <ThinkerSelector
        {...defaultProps}
        suggestions={suggestions}
        selectedThinkers={selectedThinkers}
      />
    );

    expect(screen.queryByTestId('thinker-suggestion')).toHaveTextContent(
      'Plato'
    );
    expect(screen.getAllByTestId('thinker-suggestion')).toHaveLength(1);
  });

  it('shows max thinkers message when limit reached', () => {
    const selectedThinkers = Array.from({ length: 5 }, (_, i) =>
      createSelectedThinker(`Thinker ${i}`)
    );
    render(
      <ThinkerSelector
        {...defaultProps}
        selectedThinkers={selectedThinkers}
        maxThinkers={5}
      />
    );

    expect(
      screen.getByText(/Maximum of 5 thinkers reached/)
    ).toBeInTheDocument();
  });

  it('validates custom thinker input', async () => {
    const user = userEvent.setup();
    const onValidateCustom = jest.fn().mockResolvedValue({
      name: 'Custom Thinker',
      bio: 'Bio',
      positions: 'Positions',
      style: 'Style',
    });
    const onSelect = jest.fn();

    render(
      <ThinkerSelector
        {...defaultProps}
        onValidateCustom={onValidateCustom}
        onSelect={onSelect}
      />
    );

    const input = screen.getByTestId('custom-thinker-input');
    await user.type(input, 'Custom Thinker');
    await user.click(screen.getByTestId('add-custom-thinker'));

    await waitFor(() => {
      expect(onValidateCustom).toHaveBeenCalledWith('Custom Thinker');
    });

    await waitFor(() => {
      expect(onSelect).toHaveBeenCalled();
    });
  });

  it('shows error when custom thinker validation fails', async () => {
    const user = userEvent.setup();
    const onValidateCustom = jest.fn().mockResolvedValue(null);

    render(
      <ThinkerSelector {...defaultProps} onValidateCustom={onValidateCustom} />
    );

    const input = screen.getByTestId('custom-thinker-input');
    await user.type(input, 'Unknown Person');
    await user.click(screen.getByTestId('add-custom-thinker'));

    await waitFor(() => {
      expect(screen.getByTestId('thinker-error')).toBeInTheDocument();
    });
  });
});
