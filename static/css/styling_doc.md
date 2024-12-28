# CSS Architecture Documentation

## \_base.css

**Purpose**: Provides foundational styles that form the base layer of the application's CSS architecture. These styles define the default look and behavior of basic HTML elements and establish core typographic rules.

### Contents Organization:

1. **Typography**

   - Basic text elements (`body`, `h1`-`h6`, `p`)
   - Font sizes, weights, and line heights
   - Text colors and basic text utilities

2. **Form Elements**

   - Input fields
   - Labels
   - Basic form layout
   - Form validation states

3. **Links**

   - Default link styles
   - Link states (hover, active, visited)
   - Special link types (accent, secondary)

4. **Buttons**

   - Basic button styles
   - Button states
   - Button variations

5. **Lists**

   - Unordered lists
   - Ordered lists
   - List item spacing

6. **Media**

   - Image defaults
   - Video/media element basics
   - Responsive media rules

7. **Responsive Design**
   - Base breakpoints
   - Typography scaling
   - Element spacing adjustments

### Usage Guidelines:

- Keep styles generic and reusable
- Avoid component-specific styles
- Use CSS variables from `_variables.css`
- Focus on default element styling
- Maintain a consistent typographic scale

### Dependencies:

- Requires `_variables.css` for design tokens
- Should be imported before component and layout styles

## \_variables.css

**Purpose**: Defines global CSS custom properties (variables) that maintain consistent design tokens throughout the application. This file serves as a single source of truth for colors, spacing, typography, and other design values.

### Contents Organization:

1. **Colors - Core**

   - Primary (`--primary`, `--primary-rgb`)
   - Secondary (`--secondary`, `--secondary-rgb`)
   - Accent (`--accent`, `--accent-rgb`)
   - Light (`--light`)
   - Background (`--background`)

2. **Colors - Text**

   - Base text (`--text`)
   - Muted text (`--text-muted`)
   - Dark text (`--text-dark`)
   - Light text (`--text-light`)

3. **Colors - State**

   - Warning background (`--warning-bg`)
   - Warning border (`--warning-border`)
   - Warning text (`--warning-text`)
   - Warning dark (`--warning-dark`)
   - Warning light (`--warning-light`)

4. **Colors - Status**

   - Error (`--error`, `--error-light`, `--error-dark`, `--error-border`)
   - Success (`--success`, `--success-light`, `--success-dark`, `--success-border`)
   - Warning (`--warning`, `--warning-light`, `--warning-dark`, `--warning-border`)

5. **Colors - Borders**

   - Light border (`--border-light`)
   - Input border (`--input-border`)

6. **Colors - Base**

   - White (`--color-white`)
   - Black (`--color-black`)

7. **Shadows**

   - Base shadow (`--shadow`)
   - Small shadow (`--shadow-sm`)
   - Large shadow (`--shadow-lg`)

8. **Spacing**

   - Extra small (`--spacing-xs`): 0.5rem
   - Small (`--spacing-sm`): 1rem
   - Medium (`--spacing-md`): 1.5rem
   - Large (`--spacing-lg`): 2rem
   - Extra large (`--spacing-xl`): 2.5rem
   - Extra extra large (`--spacing-xxl`): 3rem

9. **Border Radius**

   - Small (`--radius-sm`): 4px
   - Medium (`--radius-md`): 8px
   - Large (`--radius-lg`): 12px
   - Extra large (`--radius-xl`): 16px

10. **Grid**

    - Grid gap (`--grid-gap`)
    - Container width (`--container-width`)
    - Container padding (`--container-padding`)

11. **Transitions**

    - Base transition (`--transition-base`)
    - All properties (`--transition-all`)
    - Transform (`--transition-transform`)

12. **Typography**

    - Font Family
      - Base (`--font-family-base`)
    - Font Sizes
      - Extra small (`--font-size-xs`): 0.8rem
      - Small (`--font-size-sm`): 0.9rem
      - Base (`--font-size-base`): 1rem
      - Medium (`--font-size-md`): 1.1rem
      - Large (`--font-size-lg`): 1.25rem
      - Extra large (`--font-size-xl`): 1.8rem
      - Extra extra large (`--font-size-xxl`): 2.5rem
    - Font Weights
      - Normal (`--font-weight-normal`): 400
      - Medium (`--font-weight-medium`): 500
      - Semibold (`--font-weight-semibold`): 600
      - Bold (`--font-weight-bold`): 700
    - Line Heights
      - Base (`--line-height-base`): 1.5
      - Tight (`--line-height-tight`): 1.25
      - Loose (`--line-height-loose`): 1.75

13. **Opacity**

    - Disabled (`--opacity-disabled`): 0.6

14. **Breakpoints**

    - Small (`--breakpoint-sm`): 480px
    - Medium (`--breakpoint-md`): 768px
    - Large (`--breakpoint-lg`): 1024px
    - Extra large (`--breakpoint-xl`): 1280px

15. **Sizes**
    - Small icon (`--size-icon-sm`): 28px
    - Small container (`--size-container-sm`): 800px

### Usage Guidelines:

- Always use CSS variables instead of hard-coded values
- Use RGB variants for colors when opacity is needed
- Follow the naming convention: `--category-name-variant`
- Keep values consistent with design system
- Use breakpoint variables for media queries
- Use spacing variables for margins, paddings, and gaps
- Use typography variables for consistent text styling

### Dependencies:

- No dependencies
- Must be imported first in the CSS cascade

## \_components.css

**Purpose**: Contains all reusable component styles that build upon the base styles. These components are modular, self-contained UI elements that can be used across different parts of the application.

### Contents Organization:

1. **Form Components**

   - Radio groups with custom styling and hover effects
   - Input states and transitions
   - Custom radio button designs

2. **Card Components**

   - Basic card structure with shadows and hover elevation
   - Card links and view details
   - Consistent spacing and borders
   - Z-index management for hover states

3. **Warning Components**

   - Warning cards with status colors
   - Warning banners with icons
   - Warning content with consistent typography
   - Flexible content layout

4. **Info Components**

   - Info boxes with accent colors
   - Info buttons with hover states
   - Consistent spacing and borders
   - Accent color integration

5. **Button Components**

   - Accent buttons with hover effects
   - Delete buttons with error states
   - Submit buttons with success states
   - Remove buttons with icon sizing
   - Add route buttons with transitions
   - Buy coffee button with animations
   - Consistent hover and focus states

6. **Modal Components**

   - Modal overlay with backdrop blur
   - Modal content with responsive sizing
   - Section organization and spacing
   - Close button positioning
   - Consistent typography hierarchy
   - Responsive behavior

7. **Filter Components**

   - Filter groups with consistent spacing
   - Filter sections with headers
   - Filter controls alignment
   - Typography for filter labels

8. **Flash Messages**

   - Success messages with status colors
   - Error messages with status colors
   - Warning messages with status colors
   - Consistent spacing and borders
   - Center alignment and responsive width

9. **Chart Components**

   - Chart containers with responsive design
   - Chart headers with borders
   - Chart notes and titles
   - Axis styling with grid lines
   - Milestone markers with transitions
   - SVG element styling

10. **Analytics Components**

    - Analytics cards with shadows
    - Performance cards with spacing
    - Metric displays with typography
    - Consistent card styling

11. **Grade/Send Components**

    - Grade lists with consistent spacing
    - Send items with borders and shadows
    - Send details with grid layout
    - Recent sends section
    - Responsive grid adjustments

12. **Navigation Components**

    - Navbar with primary colors
    - Home icon with transitions
    - Consistent spacing and alignment

13. **Section Components**
    - Section headers with spacing
    - Consistent typography
    - Flexible layouts

### Usage Guidelines:

- Use semantic class names that describe the component's purpose
- Follow BEM naming convention for component variants
- Leverage CSS variables for consistent styling
- Keep components modular and independent
- Use responsive design patterns
- Include hover and active states
- Maintain accessibility standards
- Use provided transition variables
- Follow spacing hierarchy
- Implement consistent shadow patterns

### Dependencies:

- Requires `_variables.css` for design tokens
- Builds upon `_base.css` styles
- Should be imported after layout styles
- Uses CSS custom properties for theming

### Responsive Design:

- Components adapt to different screen sizes
- Uses breakpoint variables for consistency
- Maintains functionality across devices
- Adjusts spacing and layout as needed
- Preserves hover states on touch devices
- Ensures readability at all sizes

## \_layout.css

**Purpose**: Defines the structural layout and grid systems of the application. This file handles the positioning and arrangement of major UI sections, establishing the overall page structure and responsive grid patterns.

### Contents Organization:

1. **Container Layout**

   - Main content container
   - Maximum widths
   - Container padding
   - Background and shadows

2. **Header Layout**

   - Header structure
   - Header content wrapper
   - Header positioning
   - Header links

3. **Footer Layout**

   - Footer positioning
   - Footer spacing
   - Footer content alignment

4. **Navigation Layout**

   - Navigation structure
   - Nav links positioning
   - Navigation spacing
   - Border treatments

5. **Grid Layouts**

   - Card grid system
   - Analytics row structure
   - Metrics grid
   - Links row organization
   - Grid gaps and spacing

6. **Section Layouts**

   - Dashboard sections
   - Section spacing
   - Section backgrounds
   - Shadow treatments

7. **Visualization Layouts**

   - Visualization headers and titles
   - Filter sections and controls
   - Container structure
   - Responsive visualization wrappers
   - Filter alignment patterns

8. **Link Layouts**

   - Home link positioning
   - Feedback link positioning
   - Link spacing

9. **Responsive Layouts**
   - Large screens (1024px+)
     - Metrics grid adjustments
     - Links row modifications
     - Visualization filter layouts
   - Medium screens (768px+)
     - Container adjustments
     - Grid simplification
     - Navigation stack
     - Filter responsiveness
   - Small screens (480px+)
     - Single column layouts
     - Spacing adjustments
     - Filter stack adaptations

### Usage Guidelines:

- Use semantic class names for layout elements
- Maintain consistent spacing using variables
- Follow a mobile-first approach
- Keep layouts separate from component styles
- Use CSS Grid for complex layouts
- Use Flexbox for simpler alignments
- Maintain proper nesting of layout elements

### Dependencies:

- Requires `_variables.css` for design tokens
- Should be imported before component styles
- Works in conjunction with responsive utilities

### Grid System:

- Uses CSS Grid for main layouts
- Implements responsive breakpoints
- Maintains consistent gaps
- Adapts to content needs
- Uses auto-fit/auto-fill where appropriate

### Responsive Strategy:

- Breakpoints defined in variables
- Mobile-first approach
- Graceful degradation of layouts
- Maintains readability at all sizes
- Preserves functionality across devices

## loadingScreen.css

**Purpose**: Provides styles for the application's loading screen feature, including animations, transitions, and loading states. This file handles the visual feedback during application initialization and loading processes.

### Contents Organization:

1. **Loading Screen Variables**

   - Overlay colors
   - Background colors
   - Hover states
   - Custom loading-specific variables

2. **Loading Screen Container**

   - Full-screen overlay
   - Background image handling
   - Image transitions
   - Z-index management
   - Base animations

3. **Loading Overlay**

   - Gradient overlay
   - Opacity controls
   - Position handling

4. **Loading Content**

   - Content positioning
   - Backdrop blur effects
   - Content container styling
   - Hover interactions
   - Header styling
   - Text formatting

5. **Loading Icon**

   - Spinner animation
   - Loading icon positioning
   - Size and border controls
   - Animation timing

6. **Loading Stages**

   - Stage progression
   - Active state handling
   - Stage transitions
   - Dot indicators
   - Text styling

7. **Progress Bar**

   - Progress container
   - Progress fill animation
   - Status text
   - Loading feedback

8. **Animations**
   - Fade in/out
   - Slide up
   - Spinner rotation
   - Pulse effect
   - Image transitions
   - Background image sequences

### Usage Guidelines:

- Use loading screen for initial application load
- Maintain proper z-index hierarchy
- Follow animation timing guidelines
- Use provided variables for consistency
- Ensure proper image paths
- Handle loading states appropriately
- Consider accessibility during loading

### Dependencies:

- Requires `_variables.css` for design tokens
- Requires loading images in ../images/
- Uses backdrop-filter (check browser support)
- Relies on CSS animations

### Animation System:

- Uses keyframe animations
- Coordinated timing sequences
- Smooth transitions
- Progressive loading states
- Image crossfading
- Loading indicators

### Responsive Strategy:

- Adapts to screen sizes
- Maintains readability
- Adjusts content spacing
- Scales loading indicators
- Preserves animation smoothness

## pyramidInputs.css

This file contains styles specific to the pyramid input page functionality. It focuses on the performance table interface and related components.

### Purpose

- Provides specialized styling for the pyramid input interface
- Handles table layout and responsiveness
- Manages input groups and discipline selection
- Controls visual feedback for attempts and success/failure states

### Components

#### Performance Table

- `.chart-container`: Wrapper for the performance table with responsive behavior
- `.performance-table`: Core table styling with fixed header and column management
- Column-specific classes for width control and alignment
- Zebra striping and hover effects for rows

#### Attempts Input

- `.attempts-input-group`: Flexbox container for attempts input interface
- `.attempts-input`: Specialized number input with custom styling
- `.attempts-visual`: Visual feedback for success/failure states
- `.attempts-count`: Counter display styling

#### Table Radio Groups

- `.table-radio-group`: Custom radio button styling for table inputs
- Hidden radio inputs with styled spans for better UX
- Transition effects and visual feedback for selection states

#### Discipline Selector

- `.discipline-selector`: Layout for discipline selection interface
- `.discipline-section`: Toggle visibility of discipline-specific content
- Active state management for selected disciplines

### Dependencies

- Requires variables from `_variables.css`
- Uses common color schemes and spacing defined in base styles
- Integrates with the application's responsive design system

### Usage Guidelines

1. Maintain table column widths for consistent layout
2. Keep radio group styles consistent with the table interface
3. Ensure attempts input remains compact but usable
4. Follow the established color scheme for success/failure states
5. Preserve responsive behavior for mobile views

### Media Queries

- Table remains scrollable on smaller screens
- Input groups and radio buttons adapt to available space
- Visual feedback remains clear at all viewport sizes

## visualizations.css

**Purpose**: Provides specialized styles for data visualization components, including charts, graphs, and interactive data displays. This file focuses on SVG styling, data presentation, and visualization-specific interactions.

### Contents Organization:

1. **Chart Base Styles**

   - Performance pyramid container
   - SVG base layout
   - Responsive chart sizing
   - Chart container styling

2. **SVG Element Styles**

   - Milestone lines and text
   - Axis styling
   - Grid lines
   - SVG element transitions
   - Interactive hover states

3. **Bar Chart Styles**

   - Bar rectangles
   - Hover interactions
   - Bar labels
   - Label positioning
   - Text alignment and sizing

4. **Legend Styles**

   - Legend text formatting
   - Legend items
   - Interactive states
   - Spacing and alignment
   - Typography settings

5. **Tooltip Styles**

   - Tooltip containers
   - Content formatting
   - Strong text emphasis
   - Positioning and z-index
   - Hover interactions

6. **Data Table Styles**

   - Table containers
   - Header styling
   - Cell formatting
   - Row hover states
   - Link interactions
   - Grade headers
   - Text truncation
   - Responsive behavior

7. **Grade Line Styles**
   - Line rendering
   - Shape characteristics
   - Visual presentation

### Usage Guidelines:

- Use SVG-specific properties for vector graphics
- Maintain consistent spacing with variables
- Follow accessibility guidelines for data visualization
- Implement responsive design patterns
- Use appropriate text sizing for readability
- Handle interactive states smoothly
- Ensure proper z-index management
- Maintain consistent typography

### Dependencies:

- Requires `_variables.css` for design tokens
- Works with SVG elements and D3.js
- Uses CSS custom properties for theming
- Integrates with layout system

### SVG Styling Best Practices:

- Use `shape-rendering` appropriately
- Maintain crisp edges where needed
- Handle text alignment consistently
- Implement smooth transitions
- Manage hover states effectively
- Control opacity for interactions

### Responsive Strategy:

- Charts scale with container width
- Tables remain scrollable on small screens
- Text remains readable at all sizes
- Tooltips stay within viewport
- Maintains interaction points on touch devices

### Accessibility Considerations:

- Proper contrast ratios in data visualization
- Clear text labels and descriptions
- Interactive elements are keyboard accessible
- Screen reader friendly markup
- Appropriate ARIA attributes
