# CSS Architecture Documentation

## \_base.css

**Purpose**: Provides foundational styles that establish the core visual language and behavior of basic HTML elements across the application. This file serves as the base layer of the CSS architecture, ensuring consistent styling of fundamental elements.

### File Organization

The file is organized into five main sections, each handling different aspects of base styling:

1. **Reset & Defaults**

   - Establishes base styling for the `body` element
   - Sets foundational typography and colors
   - Enables font smoothing for better text rendering

   ```css
   body {
     font-family: var(--font-family-base);
     line-height: var(--line-height-base);
     color: var(--text);
     background-color: var(--background);
   }
   ```

2. **Typography Scale**

   - Creates a clear visual hierarchy through heading sizes
   - Establishes consistent spacing and colors
   - Defines base text styles

   | Element | Size Variable   | Color       | Spacing                         |
   | ------- | --------------- | ----------- | ------------------------------- |
   | h1      | --font-size-xxl | inherit     | margin-bottom: --spacing-lg     |
   | h2      | --font-size-xl  | --primary   | margin-bottom: --spacing-md     |
   | h3      | --font-size-lg  | --primary   | margin-bottom: --spacing-sm     |
   | h4      | --font-size-md  | --secondary | margin-bottom: --spacing-xs     |
   | p       | --font-size-sm  | --text      | line-height: --line-height-base |

3. **Interactive Elements**

   - **Links**

     - Default, accent, route, and secondary link styles
     - Consistent hover states and transitions
     - Color-coded for different purposes

   - **Buttons**

     - Reset default button styling
     - Define base button behavior
     - Handle disabled states

   - **Form Elements**
     - Consistent input, select, and textarea styling
     - Focus states with accent colors
     - Standardized padding and borders
     ```css
     input,
     select,
     textarea {
       font-family: inherit;
       font-size: var(--font-size-base);
       padding: var(--spacing-xs);
       border: 1px solid var(--input-border);
     }
     ```

4. **Content Elements**

   - **Lists**

     - Reset default list styling
     - Consistent list item spacing

   - **Media**
     - Responsive image and video handling
     - Maintain aspect ratios
     - Block display behavior

5. **Responsive Adjustments**

   - **Medium Screens** (max-width: --breakpoint-md)

     - Reduced typography scale
     - Adjusted form element sizes

   - **Small Screens** (max-width: --breakpoint-sm)
     - Further reduced typography
     - Optimized link sizes

### Usage Guidelines

1. **Variable Usage**

   - Always use CSS variables for:
     - Colors
     - Spacing
     - Typography
     - Transitions
   - This ensures consistency and makes theme changes easier

2. **Typography**

   - Use the established type scale
   - Don't override base heading colors without good reason
   - Maintain the spacing rhythm

3. **Interactive Elements**

   - Build upon these base styles rather than overriding them
   - Maintain consistent focus states for accessibility
   - Use provided transition variables

4. **Responsive Design**
   - Follow the established breakpoints
   - Use the provided responsive adjustments as a foundation
   - Add component-specific responsive behavior in component files

### Best Practices

1. **Inheritance**

   - Use `inherit` for font properties where possible
   - Leverage cascading for consistent typography

2. **Accessibility**

   - Maintain sufficient color contrast
   - Keep focus states visible
   - Use semantic HTML elements

3. **Performance**
   - Avoid overriding base styles repeatedly
   - Use the provided CSS variables
   - Keep specificity low

### Dependencies

- Requires `_variables.css` for design tokens
- Should be imported before component styles
- Must be included in the main stylesheet

### Example Usage

```css
// Building upon base styles
.custom-heading {
  /* Extends h2 styles */
  font-size: var(--font-size-xl);
  color: var(--primary);
  /* Add custom modifications */
  text-transform: uppercase;
}

.custom-input {
  /* Inherits base input styles */
  /* Add specific modifications */
  border-width: 2px;
  padding: var(--spacing-sm);
}
```

## \_variables.css

**Purpose**: Defines the global CSS custom properties (variables) that maintain consistent design tokens throughout the application. This file serves as the single source of truth for the design system.

### Color System

#### Brand Colors

```css
--primary: #2a4f5f      /* Main brand color */
--secondary: #7ea88b    /* Secondary brand color */
--accent: #6cb2eb       /* Accent for CTAs and highlights */
--light: #f6b17a        /* Light accent color */
--background: #f7f9fc   /* Default background */
```

RGB variants (`--primary-rgb`, etc.) are provided for opacity/alpha operations.

#### Extended Color Palette

```css
--accent-coral: #ff6b6b     /* Vibrant red-orange */
--accent-peach: #ffb4a2     /* Soft coral */
--accent-gold: #ffd93d      /* Bright yellow */
--accent-teal: #4ecdc4      /* Bright teal */
--accent-lavender: #6c63ff  /* Purple */
--accent-sky: #6cb2eb       /* Light blue */
```

#### Status Colors

Each status has four variants:

```css
/* Example: Success */
--success: #2e7d32         /* Base */
--success-light: #dcfce7   /* Background */
--success-dark: #166534    /* Text/Icons */
--success-border: #bbf7d0  /* Borders */
```

Similar patterns for `error` and `warning`.

### Typography System

#### Font Scale

```css
--font-size-xs: 0.8rem    /* Small labels */
--font-size-sm: 0.9rem    /* Secondary text */
--font-size-base: 1rem    /* Body text */
--font-size-md: 1.1rem    /* Emphasized text */
--font-size-lg: 1.25rem   /* Subheadings */
--font-size-xl: 1.8rem    /* Headings */
--font-size-xxl: 2.5rem   /* Hero text */
```

#### Font Weights

```css
--font-weight-normal: 400    /* Body text */
--font-weight-medium: 500    /* Slightly emphasized */
--font-weight-semibold: 600  /* Subheadings */
--font-weight-bold: 700      /* Headings */
```

#### Line Heights

```css
--line-height-tight: 1.25  /* Headings */
--line-height-base: 1.5    /* Body text */
--line-height-loose: 1.75  /* Large text blocks */
```

### Spacing System

#### Base Spacing Scale

```css
--spacing-xs: 0.5rem   /* Tight spacing */
--spacing-sm: 1rem     /* Default spacing */
--spacing-md: 1.5rem   /* Medium spacing */
--spacing-lg: 2rem     /* Section spacing */
--spacing-xl: 2.5rem   /* Large sections */
--spacing-xxl: 3rem    /* Page sections */
```

#### Grid System

```css
--grid-gap: 1.5rem         /* Default grid spacing */
--container-width: 1200px  /* Max content width */
--container-padding: 2rem  /* Container edge spacing */
```

### Visual Style

#### Border Radius

```css
--radius-sm: 4px    /* Buttons, inputs */
--radius-md: 8px    /* Cards, panels */
--radius-lg: 12px   /* Large cards */
--radius-xl: 16px   /* Modal, dialogs */
```

#### Shadows

```css
--shadow-sm: 0 2px 4px rgba(0,0,0,0.05)     /* Subtle elevation */
--shadow: [multiple layers]                  /* Default elevation */
--shadow-lg: 0 4px 20px rgba(0,0,0,0.15)    /* High elevation */
```

#### Transitions

```css
--transition-base: 0.2s ease          /* Default */
--transition-all: all 0.15s ease      /* Full element */
--transition-transform: transform 0.2s /* Movement only */
```

### Breakpoints

```css
--breakpoint-sm: 480px   /* Mobile */
--breakpoint-md: 768px   /* Tablet */
--breakpoint-lg: 1024px  /* Desktop */
--breakpoint-xl: 1280px  /* Large desktop */
```

### Usage Guidelines

1. **Color Usage**

   - Use semantic color names (e.g., `--primary` not `--blue`)
   - Use RGB variants for opacity: `rgba(var(--primary-rgb), 0.5)`
   - Status colors include context variants (light/dark/border)

2. **Typography**

   - Use relative units (rem) for font sizes
   - Follow the type scale for hierarchy
   - Use appropriate line heights for content type

3. **Spacing**

   - Use spacing scale for consistency
   - Combine values for larger spaces
   - Use grid variables for layouts

4. **Responsive Design**
   - Use breakpoint variables in media queries
   - Follow mobile-first approach
   ```css
   @media (min-width: var(--breakpoint-md)) {
     /* Tablet and up */
   }
   ```

### Best Practices

1. **Variable Naming**

   - Use semantic names
   - Follow `--category-name-variant` pattern
   - Be consistent with naming conventions

2. **Color Management**

   - Keep RGB variants for opacity
   - Use HSL for color variations
   - Maintain consistent status color patterns

3. **Maintainability**

   - Document significant changes
   - Keep variables organized by category
   - Use comments to explain non-obvious values

4. **Performance**
   - Minimize redundant variables
   - Use calculated values where appropriate
   - Keep specificity low

### Common Patterns

1. **Color with Opacity**

   ```css
   background: rgba(var(--primary-rgb), 0.1);
   ```

2. **Spacing Combinations**

   ```css
   margin: var(--spacing-sm) var(--spacing-lg);
   ```

3. **Responsive Containers**

   ```css
   max-width: var(--container-width);
   padding: var(--container-padding);
   ```

4. **Shadow Layering**
   ```css
   box-shadow: var(--shadow);
   transition: var(--transition-all);
   ```

### Dependencies

- No dependencies
- Must be imported first in stylesheet cascade
- Required by all other CSS files

## \_components.css

**Purpose**: Provides reusable UI components and patterns that form the building blocks of the application's interface. This file contains all styled components, from basic inputs to complex dashboard elements.

### File Organization

The file is organized into logical component groups, each serving specific UI needs:

1. **Input Components**

   - Radio Groups
   - Visualization Radio Groups

   ```css
   .radio-group {
     display: flex;
     gap: var(--spacing-sm);
     flex-wrap: wrap;
   }
   ```

2. **Button Components**

   - Primary Buttons (`.accent-button`, `.submit-btn`)
   - Secondary Buttons (`.discipline-btn`, `.add-route-btn`)
   - Danger Buttons (`.delete-btn`, `.remove-btn`)
   - Utility Buttons (`.buy-coffee-button`, `.info-button`, `.refresh-button`)

3. **Card Components**

   - Base Card Structure
   - Card Content Layout
   - Specialized Cards (Warning, Performance)

   ```css
   .card {
     background: var(--background);
     border-radius: var(--radius-md);
     transition: all var(--transition-base);
     overflow: hidden;
     position: relative;
   }
   ```

4. **Modal Components**

   - Modal Container
   - Modal Content
   - Modal Sections
   - Close Buttons

5. **Notification Components**

   - Flash Messages (Success, Error, Warning)
   - Warning Banners
   - Info Boxes

6. **Filter Components**

   - Filter Groups
   - Filter Sections
   - Filter Controls

7. **Visualization Components**

   - Chart Container
   - Chart Header
   - Chart Elements (Axis, Grid)
   - Milestone Components

8. **Dashboard Components**

   - Quick Stats
   - Metrics Grid
   - Metric Colors

9. **Grade Components**

   - Grade Lists
   - Grade Items
   - Grade Styling

10. **Recent Sends Components**
    - Send Lists
    - Send Items
    - Discipline Indicators

### Component Patterns

#### Interactive States

All interactive components follow these patterns:

```css
/* Hover State */
component:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

/* Active/Selected State */
component.active {
  background-color: var(--accent);
  color: var(--color-white);
}
```

#### Color Usage

- Primary Actions: `var(--accent)`
- Secondary Actions: `var(--secondary)`
- Danger Actions: `var(--error)`
- Success States: `var(--success-*)`
- Warning States: `var(--warning-*)`

#### Spacing Patterns

- Small Components: `var(--spacing-xs)` to `var(--spacing-sm)`
- Medium Components: `var(--spacing-md)`
- Large Components: `var(--spacing-lg)` to `var(--spacing-xl)`
- Container Padding: `var(--spacing-lg)` to `var(--spacing-xl)`

### Usage Guidelines

1. **Button Usage**

   - Use `.accent-button` for primary actions
   - Use `.submit-btn` for form submissions
   - Use `.delete-btn` for destructive actions
   - Use `.info-button` for help/information triggers

2. **Card Implementation**

   ```css
   <div class="card">
     <a class="card-link">
       <h3>Title</h3>
       <p>Content</p>
     </a>
   </div>
   ```

3. **Notification System**

   - Use `.flash-message.success` for success messages
   - Use `.flash-message.error` for error messages
   - Use `.flash-message.warning` for warning messages

4. **Dashboard Metrics**
   ```css
   <div class="dashboard-quick-stats">
     <div class="metrics-grid">
       <div class="metric">
         <span class="metric-label">Label</span>
         <span class="metric-value">Value</span>
       </div>
     </div>
   </div>
   ```

### Responsive Design

The components use these breakpoints:

- Medium: `var(--breakpoint-md)` - 768px
- Small: `var(--breakpoint-sm)` - 480px

Key responsive adjustments:

```css
@media (max-width: var(--breakpoint-md)) {
  /* Reduced padding */
  /* Simplified layouts */
  /* Adjusted grid columns */
}

@media (max-width: var(--breakpoint-sm)) {
  /* Single column layouts */
  /* Further simplified components */
}
```

### Best Practices

1. **Component Structure**

   - Keep components modular and independent
   - Use BEM-like naming for component variants
   - Maintain consistent spacing patterns

2. **Interaction Design**

   - Use transitions for all interactive states
   - Maintain hover and focus states
   - Provide visual feedback for actions

3. **Accessibility**

   - Ensure sufficient color contrast
   - Maintain focus visibility
   - Use semantic HTML elements

4. **Performance**
   - Use CSS transforms for animations
   - Minimize complex selectors
   - Optimize transition properties

### Dependencies

- Requires `_variables.css` for design tokens
- Builds upon `_base.css` styles
- Should be imported after base styles

### Example Usage

```html
<!-- Button Example -->
<button class="accent-button">
  <i class="icon"></i>
  <span>Action</span>
</button>

<!-- Card Example -->
<div class="card">
  <div class="card-link">
    <h3>Card Title</h3>
    <p>Card content goes here</p>
  </div>
</div>

<!-- Notification Example -->
<div class="flash-messages">
  <div class="flash-message success">Success message</div>
</div>
```

### Common Patterns

1. **Elevation on Hover**

   ```css
   element:hover {
     transform: translateY(-1px);
     box-shadow: var(--shadow-sm);
   }
   ```

2. **Color Transitions**

   ```css
   element {
     transition: var(--transition-all);
   }
   ```

3. **Grid Layouts**

   ```css
   container {
     display: grid;
     grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
     gap: var(--spacing-lg);
   }
   ```

4. **Responsive Patterns**
   ```css
   @media (max-width: var(--breakpoint-md)) {
     container {
       grid-template-columns: repeat(2, 1fr);
     }
   }
   ```

## \_layout.css

**Purpose**: Defines the core structural layout and grid systems for the application. This file establishes the foundational layout patterns, spacing, and responsive behavior for major page sections.

### File Organization

The file is organized into eight main sections:

1. **Main Container**

   - Defines the primary content wrapper
   - Sets maximum width constraints
   - Establishes base spacing and visual treatment

   ```css
   main {
     max-width: var(--container-width);
     margin: var(--spacing-lg) auto;
     padding: var(--spacing-lg);
   }
   ```

2. **Header Components**

   - **Primary Header**: Main navigation bar
   - **Header Content**: Content wrapper and spacing
   - **Header Links**: Navigation and action links

   ```css
   header {
     background-color: var(--primary);
     display: flex;
     justify-content: space-between;
     align-items: center;
   }
   ```

3. **Footer Components**

   - Base footer structure
   - Footer navigation
   - Footer links and icons

   ```css
   .footer-nav {
     display: flex;
     justify-content: center;
     align-items: center;
     gap: var(--spacing-xl);
   }
   ```

4. **Grid Systems**
   | Grid Type | Columns | Use Case |
   |-----------|---------|----------|
   | Card Grid | auto-fit, minmax(300px, 1fr) | Card layouts |
   | Analytics | Full width | Data displays |
   | Metrics | 5 columns | Dashboard metrics |
   | Links | 3 columns | Navigation links |

5. **Section Layouts**

   - Dashboard sections
   - Content blocks
   - Spacing patterns

6. **Link Layouts**

   - Standalone links
   - Link groups
   - Link positioning

7. **Visualization Layouts**

   - Visualization headers
   - Filter sections
   - Container constraints
   - Overflow handling

8. **Responsive Adjustments**
   - Large screens (1024px)
   - Medium screens (768px)
   - Small screens (480px)

### Layout Patterns

#### Container Widths

```css
/* Maximum width constraint */
max-width: var(--container-width);
margin: 0 auto;

/* Fluid width with padding */
width: calc(100% - var(--spacing-md) * 2);
```

#### Flexbox Patterns

```css
/* Center alignment */
display: flex;
justify-content: center;
align-items: center;

/* Space between */
display: flex;
justify-content: space-between;
align-items: center;
```

#### Grid Patterns

```css
/* Responsive card grid */
display: grid;
grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
gap: var(--grid-gap);

/* Fixed column grid */
display: grid;
grid-template-columns: repeat(5, 1fr);
gap: var(--spacing-md);
```

### Usage Guidelines

1. **Container Usage**

   - Use `main` for primary content wrapper
   - Maintain consistent max-width constraints
   - Apply appropriate spacing variables

2. **Grid Implementation**

   - Use `card-grid` for card-based layouts
   - Use `metrics-grid` for dashboard metrics
   - Use `analytics-row` for full-width data displays

3. **Header Structure**

   ```html
   <header>
     <div class="header-content">
       <div class="header-wrapper">
         <!-- Header content -->
       </div>
     </div>
   </header>
   ```

4. **Visualization Layout**
   ```html
   <div class="viz-container">
     <div class="viz-header">
       <div class="viz-title">
         <h2>Title</h2>
       </div>
       <div class="viz-filters">
         <!-- Filters -->
       </div>
     </div>
   </div>
   ```

### Responsive Design

#### Breakpoints

- Large: `var(--breakpoint-lg)` - 1024px

  ```css
  /* Grid adjustments */
  .metrics-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .links-row {
    grid-template-columns: repeat(2, 1fr);
  }
  ```

- Medium: `var(--breakpoint-md)` - 768px

  ```css
  /* Layout simplification */
  .card-grid {
    grid-template-columns: 1fr;
  }
  .nav-links {
    flex-direction: column;
  }
  ```

- Small: `var(--breakpoint-sm)` - 480px
  ```css
  /* Single column layouts */
  .metrics-grid {
    grid-template-columns: 1fr;
  }
  ```

### Best Practices

1. **Layout Structure**

   - Use semantic HTML elements
   - Maintain consistent spacing
   - Follow mobile-first approach

2. **Grid Usage**

   - Use appropriate grid system for content type
   - Consider responsive breakpoints
   - Maintain consistent gaps

3. **Spacing**

   - Use spacing variables consistently
   - Maintain rhythm between sections
   - Consider mobile spacing needs

4. **Performance**
   - Use appropriate units (rem, em)
   - Optimize for reflow
   - Consider paint performance

### Dependencies

- Requires `_variables.css` for design tokens
- Should be imported before component styles
- Works in conjunction with responsive utilities

### Example Implementations

1. **Dashboard Section**

   ```html
   <section class="dashboard-section">
     <div class="metrics-grid">
       <!-- Metric items -->
     </div>
   </section>
   ```

2. **Card Layout**

   ```html
   <div class="card-grid">
     <div class="card">
       <!-- Card content -->
     </div>
   </div>
   ```

3. **Visualization Section**
   ```html
   <div class="viz-container">
     <div class="viz-header">
       <!-- Visualization header -->
     </div>
     <!-- Visualization content -->
   </div>
   ```

### Common Patterns

1. **Section Spacing**

   ```css
   .section {
     margin-bottom: var(--spacing-xxl);
     padding: var(--spacing-lg);
   }
   ```

2. **Responsive Containers**

   ```css
   .container {
     max-width: var(--container-width);
     padding: var(--spacing-md);
     margin: 0 auto;
   }
   ```

3. **Flex Layouts**

   ```css
   .flex-container {
     display: flex;
     align-items: center;
     gap: var(--spacing-md);
   }
   ```

4. **Grid Layouts**
   ```css
   .grid-container {
     display: grid;
     grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
     gap: var(--spacing-lg);
   }
   ```

## loadingScreen.css

**Purpose**: Provides styles for the application's loading screen, featuring animated background transitions, loading stages, and visual feedback.

### File Organization

1. **Custom Properties**

   ```css
   :root {
     --loading-overlay: rgba(45, 50, 80, 0.5);
     --loading-content-bg: rgba(255, 255, 255, 0.45);
   }
   ```

   - Consistent colors
   - Configurable opacity
   - Reusable values

2. **Loading Container**

   ```css
   #loadingScreen {
     position: fixed;
     z-index: 9999;
     opacity: 0;
     animation: fadeIn var(--transition-base) forwards;
   }
   ```

   - Full screen overlay
   - Proper z-indexing
   - Smooth entrance

3. **Background System**

   ```css
   #loadingScreen::before,
   #loadingScreen::after {
     background-size: cover;
     background-position: center;
     transition: opacity 1s ease-in-out;
   }
   ```

   - Dual background system
   - Smooth transitions
   - Responsive images

4. **Content Card**

   ```css
   .loading-content {
     background: var(--loading-content-bg);
     backdrop-filter: blur(8px);
     width: 90%;
     max-width: 600px;
   }
   ```

   - Glass morphism effect
   - Responsive sizing
   - Proper positioning

5. **Loading Indicators**
   | Component | Size | Animation |
   |-----------|------|-----------|
   | Spinner | 50px/40px | Continuous rotation |
   | Stage Dot | 12px/10px | Pulse effect |
   | Progress Bar | 6px height | Width transition |

6. **Stage System**

   ```css
   .stage {
     opacity: 0.5;
     transform: translateX(-10px);
   }
   .stage.active {
     opacity: 1;
     transform: translateX(0);
   }
   ```

   - Visual progression
   - Smooth transitions
   - Clear active states

7. **Responsive Design**
   ```css
   @media (max-width: var(--breakpoint-sm)) {
     .loading-content {
       width: 94%;
       padding: var(--spacing-lg);
     }
   }
   ```
   - Mobile optimizations
   - Proper spacing
   - Touch-friendly
   - Readable text

### Animation System

1. **Entrance Animations**

   - FadeIn for screen
   - SlideUp for content
   - Staggered timing

2. **Loading Animations**

   - Spinner rotation
   - Stage transitions
   - Progress bar

3. **Background Transitions**
   - 35s cycle
   - 5 background images
   - Smooth opacity changes

### Best Practices

1. **Performance**

   - Hardware acceleration
   - Efficient animations
   - Image optimization
   - Smooth transitions

2. **Accessibility**

   - ARIA attributes
   - Progress feedback
   - Clear status text
   - Proper contrast

3. **Responsiveness**

   - Mobile-first
   - Touch-friendly
   - Flexible layouts
   - Proper spacing

4. **Visual Feedback**
   - Clear progression
   - Smooth animations
   - Status updates
   - Loading indicators

### Dependencies

- Requires `_variables.css` for design tokens
- Needs loading images:
  - loading1.jpg through loading5.jpg
- Uses modern CSS features:
  - backdrop-filter
  - CSS animations
  - transforms

### Common Patterns

1. **Stage Management**

   ```css
   .stage {
     opacity: 0.5;
     transition: var(--transition-all);
   }
   .stage.active {
     opacity: 1;
     background: rgba(var(--accent-rgb), 0.1);
   }
   ```

2. **Loading States**

   ```css
   .loading-icon {
     display: flex;
     justify-content: center;
   }
   .spinner {
     animation: spin 0.8s infinite;
   }
   ```

3. **Content Transitions**
   ```css
   .loading-content {
     animation: slideUp 0.4s ease forwards;
     transition: background-color var(--transition-base);
   }
   ```

### Known Issues

1. **Background Images**

   - Heavy resource usage
   - May need preloading
   - Mobile bandwidth consideration

2. **Glass Effect**

   - Performance impact
   - Browser support varies
   - Fallback needed

3. **Animations**
   - CPU intensive
   - Battery impact on mobile
   - May need reduced motion support

## pyramidInputs.css

**Purpose**: Provides specialized styles for the pyramid input interface, focusing on the performance table, input controls, and discipline selection components.

### File Organization

The file is organized into five main sections:

1. **Performance Table**

   ```css
   .chart-container {
     border-radius: var(--radius-lg);
     box-shadow: var(--shadow);
     overflow-x: auto;
     -webkit-overflow-scrolling: touch;
   }
   ```

   | Column         | Width | Min-Width | Purpose          |
   | -------------- | ----- | --------- | ---------------- |
   | Number         | 3%    | 40px      | Row numbering    |
   | Route Name     | 12%   | 120px     | Route identifier |
   | Date           | 8%    | 100px     | Completion date  |
   | Grade          | 6%    | 70px      | Difficulty grade |
   | Attempts       | 8%    | 100px     | Try count        |
   | Characteristic | 15%   | 160px     | Route features   |
   | Style          | 15%   | 160px     | Climbing style   |
   | Actions        | 4%    | 50px      | Row controls     |

2. **Input Components**

   - Attempts Input
     ```css
     .attempts-input {
       width: 35px;
       text-align: center;
       border-radius: var(--radius-sm);
     }
     ```
   - Focus States
   - Number Controls
   - Input Groups

3. **Radio Components**

   ```css
   .table-radio-group {
     display: flex;
     flex-wrap: wrap;
     gap: var(--spacing-xs);
   }
   ```

   - Custom Radio Design
   - Hidden Input Pattern
   - Visual States
   - Label Styling

4. **Discipline Components**

   ```css
   .discipline-selector {
     display: flex;
     justify-content: center;
     gap: var(--spacing-sm);
   }
   ```

   - Section Toggle
   - Active States
   - Layout Control

5. **Visual Feedback**
   ```css
   .attempts-visual {
     display: flex;
     align-items: center;
     gap: var(--spacing-xs);
   }
   ```
   - Success/Failure States
   - Count Display
   - Status Indicators

### Usage Guidelines

1. **Table Implementation**

   ```html
   <div class="chart-container">
     <table class="performance-table">
       <thead>
         <tr>
           <th class="number-column">#</th>
           <th class="route-name-column">Route</th>
           <!-- Additional columns -->
         </tr>
       </thead>
     </table>
   </div>
   ```

2. **Input Controls**

   ```html
   <div class="attempts-input-group">
     <input type="number" class="attempts-input" />
     <div class="attempts-visual">
       <!-- Status indicators -->
     </div>
   </div>
   ```

3. **Radio Groups**

   ```html
   <div class="table-radio-group">
     <label>
       <input type="radio" name="group" />
       <span>Option</span>
     </label>
   </div>
   ```

4. **Discipline Selection**
   ```html
   <div class="discipline-selector">
     <!-- Discipline options -->
   </div>
   <div class="discipline-section">
     <!-- Section content -->
   </div>
   ```

### Component Patterns

1. **Table Scrolling**

   ```css
    {
     overflow-x: auto;
     -webkit-overflow-scrolling: touch;
     width: 100%;
     max-width: 100%;
   }
   ```

2. **Input Styling**

   ```css
    {
     border: 1px solid var(--input-border);
     transition: var(--transition-base);
   }
   ```

3. **Radio Design**
   ```css
   input[type="radio"] {
     position: absolute;
     opacity: 0;
   }
   input[type="radio"] + span {
     /* Visual representation */
   }
   ```

### Best Practices

1. **Table Structure**

   - Use semantic table markup
   - Maintain column width ratios
   - Handle overflow gracefully
   - Implement sticky headers

2. **Input Handling**

   - Clear focus states
   - Proper input validation
   - Visual feedback
   - Touch-friendly targets

3. **Radio Groups**

   - Accessible markup
   - Clear visual states
   - Consistent spacing
   - Proper grouping

4. **Visual States**
   - Clear success/failure indicators
   - Consistent color usage
   - Appropriate transitions
   - Hover feedback

### Dependencies

- Requires `_variables.css` for design tokens
- Uses CSS custom properties for theming
- Relies on flexbox for layout
- Requires modern browser support

### Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Mobile browsers with touch support
- Fallbacks for:
  - Sticky positioning
  - Custom radio styling
  - Touch scrolling

### Common Patterns

1. **Column Widths**

   ```css
   .column {
     width: percentage;
     min-width: fixed-px;
   }
   ```

2. **Input States**

   ```css
   .input:focus {
     border-color: var(--accent);
     box-shadow: 0 0 0 2px rgba(var(--accent-rgb), 0.1);
   }
   ```

3. **Radio Toggles**
   ```css
   input[type="radio"]:checked + span {
     background-color: var(--accent);
     color: var(--color-white);
   }
   ```

### Known Issues

1. **Table Scrolling**

   - May require horizontal scroll on small screens
   - Touch scrolling needs -webkit prefix
   - Sticky headers may jump in some browsers

2. **Input Numbers**

   - Spinner removal needs vendor prefixes
   - Width constraints may clip longer numbers
   - Mobile keyboard might not show number pad

3. **Radio Groups**
   - Custom styling requires hidden input pattern
   - Focus states need explicit handling
   - Layout may break with long labels

## visualizations.css

**Purpose**: Provides specialized styles for data visualization components, including charts, graphs, and interactive data displays. This file focuses on SVG styling, data presentation, and visualization-specific interactions.

### File Organization

The file is organized into seven main sections:

1. **Performance Pyramid**

   ```css
   #performance-pyramid {
     overflow-x: auto;
     overflow-y: hidden;
     -webkit-overflow-scrolling: touch;
   }
   ```

   - Responsive container
   - Touch scrolling support
   - Minimum width constraints

2. **Chart Elements**
   | Element | Purpose | Interaction |
   |---------|---------|-------------|
   | Milestones | Progress markers | Hover reveals text |
   | Axis | Data scales | Static display |
   | Grid | Reference lines | Static background |

3. **Bar Chart Components**

   ```css
   .bar rect {
     transition: var(--transition-all);
   }
   .bar-labels text {
     font-size: var(--font-size-sm);
     letter-spacing: -0.02em;
   }
   ```

   - Bar rectangles
   - Label positioning
   - Hover states

4. **Legend Components**

   ```css
   .legend-item {
     cursor: default;
     opacity: 1;
     transition: var(--transition-base);
   }
   ```

   - Text styling
   - Interactive states
   - Hover effects

5. **Tooltip Components**

   ```css
   .pyramid-tooltip {
     pointer-events: none;
     z-index: 1000;
     box-shadow: var(--shadow-sm);
   }
   ```

   - Positioning
   - Content formatting
   - Visual styling

6. **Data Table Components**

   - Table structure
   - Cell formatting
   - Grade headers
   - Responsive behavior

7. **Grade Line Components**
   - Line rendering
   - Visual properties

### SVG Styling Patterns

1. **Text Elements**

   ```css
   text {
     font-size: var(--font-size-xs);
     fill: var(--text);
     letter-spacing: -0.02em;
   }
   ```

2. **Interactive Elements**

   ```css
   .interactive-element {
     transition: var(--transition-base);
     cursor: default;
   }
   ```

3. **Lines and Paths**
   ```css
   line,
   path {
     stroke: var(--border-light);
     transition: var(--transition-base);
   }
   ```

### Usage Guidelines

1. **Chart Implementation**

   ```html
   <div id="performance-pyramid">
     <svg>
       <!-- Chart elements -->
       <g class="viz-milestone">
         <line />
         <text />
       </g>
     </svg>
   </div>
   ```

2. **Table Structure**

   ```html
   <div class="projects-table-container">
     <table class="data-table">
       <thead>
         <tr>
           <th>Header</th>
         </tr>
       </thead>
       <tbody>
         <!-- Data rows -->
       </tbody>
     </table>
   </div>
   ```

3. **Tooltip Integration**
   ```html
   <div class="pyramid-tooltip">
     <div class="tooltip-content">
       <strong>Label</strong>
       <span>Value</span>
     </div>
   </div>
   ```

### Best Practices

1. **SVG Performance**

   - Use `shape-rendering` appropriately
   - Minimize path complexity
   - Optimize animations
   - Handle large datasets efficiently

2. **Accessibility**

   - Provide ARIA labels
   - Include descriptive text
   - Maintain color contrast
   - Support keyboard navigation

3. **Responsiveness**

   - Handle overflow gracefully
   - Scale text appropriately
   - Maintain touch targets
   - Support mobile interactions

4. **Interactions**
   - Clear hover states
   - Smooth transitions
   - Informative tooltips
   - Consistent feedback

### Dependencies

- Requires `_variables.css` for design tokens
- Works with SVG elements
- Integrates with D3.js or similar libraries
- Uses modern CSS features

### Common Patterns

1. **Hover Effects**

   ```css
   element:hover {
     opacity: var(--opacity-disabled);
     transform: translateX(-3px);
   }
   ```

2. **Text Truncation**

   ```css
   .truncate {
     white-space: nowrap;
     overflow: hidden;
     text-overflow: ellipsis;
   }
   ```

3. **Responsive Tables**
   ```css
   .table-container {
     overflow-x: auto;
     -webkit-overflow-scrolling: touch;
   }
   ```

### Known Issues

1. **SVG Text**

   - Font rendering inconsistencies
   - Scaling challenges
   - Line height handling
   - Text alignment quirks

2. **Touch Interactions**

   - Tooltip positioning on mobile
   - Small target areas
   - Scroll vs. swipe conflicts
   - Hover state alternatives

3. **Performance**
   - Large dataset rendering
   - Animation smoothness
   - Memory management
   - Mobile optimization

### Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- SVG support required
- Touch events for mobile
- CSS variables support

### Animation Guidelines

1. **Transitions**

   ```css
   .animated-element {
     transition: var(--transition-base);
     transform: translateX(0);
   }
   ```

2. **Hover States**

   ```css
   .hover-element:hover {
     opacity: 1;
     transform: translateX(-3px);
   }
   ```

3. **Loading States**
   ```css
   .loading {
     opacity: 0.5;
     pointer-events: none;
   }
   ```

### Data Visualization Tips

1. **Color Usage**

   - Use semantic colors
   - Maintain contrast
   - Consider color blindness
   - Consistent meaning

2. **Typography**

   - Scale appropriately
   - Clear hierarchy
   - Readable sizes
   - Consistent spacing

3. **Interaction Design**
   - Clear feedback
   - Intuitive behavior
   - Smooth transitions
   - Error prevention

## \_landingPage.css

**Purpose**: Provides styles specific to the landing/home page of the application, featuring a full-screen background image, centered content card, and interactive form elements.

### File Organization

The file is organized into eight main sections:

1. **Base Reset & Container**

   ```css
   html,
   body {
     margin: 0;
     padding: 0;
     height: 100%;
     overflow: hidden;
   }
   .container {
     min-height: 100vh;
     display: flex;
     flex-direction: column;
     z-index: 1;
   }
   ```

   - Prevents scrolling on landing
   - Full viewport height container
   - Proper z-indexing

2. **Background & Layout**

   ```css
   .background-overlay {
     background-image: linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.6)),
       url("../images/index_background.jpg");
     background-size: cover;
     background-position: center;
   }
   ```

   - Fixed position overlay
   - Gradient overlay for text contrast
   - Responsive background image

3. **Main Content**

   ```css
   .main-content {
     background: rgba(255, 255, 255, 0.45);
     backdrop-filter: blur(8px);
     width: 280px;
     max-width: 320px;
     border-radius: 20px;
   }
   ```

   - Glass morphism effect
   - Fixed width for consistency
   - Responsive padding
   - Centered alignment

4. **Form Elements**

   ```css
   .input-container input[type="url"] {
     width: 280px;
     padding: 12px;
     text-align: center;
     min-height: 44px;
   }
   ```

   - URL input optimization
   - Consistent width with buttons
   - Touch-friendly sizing
   - Centered text alignment

5. **Button Components**
   | Button Type | Width | Padding | Height |
   |-------------|--------|---------|---------|
   | Primary & Secondary | 280px | 12px | 44px min |
   | Desktop | 400px | 16px | 44px min |

6. **Footer**

   ```css
   footer {
     position: fixed;
     background: rgba(42, 79, 95, 0.98);
     backdrop-filter: blur(8px);
   }
   .footer-links {
     gap: 32px;
     width: 375px;
   }
   ```

   - Fixed positioning
   - Semi-transparent background
   - Consistent link spacing
   - Mobile optimizations

7. **Loading States**

   ```css
   .loading-spinner {
     border: 2px solid rgba(255, 255, 255, 0.3);
     animation: spin 0.8s linear infinite;
   }
   ```

   - Button loading indicators
   - Smooth animations
   - Color variations

8. **Responsive Design**
   ```css
   @media (min-width: var(--breakpoint-md)) {
     .main-content {
       width: 440px;
       max-width: 480px;
     }
     input[type="url"],
     .button-group {
       width: 400px;
     }
   }
   ```
   - Mobile-first approach
   - Consistent element sizing
   - Touch-friendly targets
   - Responsive typography

### Best Practices

1. **Layout**

   - Fixed widths for consistency
   - Proper element alignment
   - Touch-friendly sizing
   - Consistent spacing

2. **Typography**

   - Responsive font sizes
   - Clear hierarchy
   - Proper line heights
   - Mobile optimization

3. **Interactions**

   - Clear focus states
   - Smooth transitions
   - Loading indicators
   - Error states

4. **Mobile**
   - No horizontal scroll
   - Touch-friendly targets
   - Readable text sizes
   - Proper spacing

## style.css

**Purpose**: Main stylesheet entry point that manages the import order of all CSS modules, ensuring proper cascade and dependency resolution.

### File Organization

```css
/* Import base styles */
@import "_variables.css"; /* Design tokens and variables */
@import "_base.css"; /* Base element styles */
@import "_layout.css"; /* Layout and grid systems */
@import "_components.css"; /* Reusable components */

/* Import feature-specific styles */
@import "loadingScreen.css"; /* Loading screen styles */
@import "pyramidInputs.css"; /* Pyramid input interface */
@import "visualizations.css"; /* Data visualization styles */
```

### Import Order

1. **Core Styles**

   - `_variables.css`: Must be first to make variables available
   - `_base.css`: Establishes foundational styles
   - `_layout.css`: Defines structural layout
   - `_components.css`: Adds reusable components

2. **Feature Styles**
   - `loadingScreen.css`: Loading screen specifics
   - `pyramidInputs.css`: Pyramid interface styles
   - `visualizations.css`: Chart and graph styles

### Usage Guidelines

1. **Import Management**

   - Maintain this order for proper cascade
   - Core styles before feature styles
   - Variables must be first

2. **Adding New Styles**
   - Feature styles go after core imports
   - Keep related styles grouped
   - Consider dependencies

### Best Practices

1. **File Organization**

   - Use underscore prefix for partials
   - Group related imports
   - Comment import sections

2. **Performance**
   - Consider using CSS bundling
   - Minimize import chains
   - Watch for duplicates

### Dependencies

- All imported files must exist
- Files must be in correct relative paths
- Modern browser @import support

## Responsive Design System

### Overview

The responsive design system is built on a mobile-first approach using CSS custom properties and utility classes. It provides consistent breakpoints, fluid typography, and responsive layouts across the application.

### Breakpoints

```css
--breakpoint-xs: 320px  /* Small phones */
--breakpoint-sm: 480px  /* Large phones */
--breakpoint-md: 768px  /* Tablets */
--breakpoint-lg: 1024px /* Laptops/Desktops */
--breakpoint-xl: 1280px /* Large Desktops */
```

### Container System

The container system automatically handles responsive widths:

```css
--container-sm: 100%    /* Mobile */
--container-md: 720px   /* Tablet */
--container-lg: 960px   /* Laptop */
--container-xl: 1140px  /* Desktop */
```

Usage:

```html
<div class="container">
  <!-- Content automatically responds to screen size -->
</div>
```

### Responsive Grid System

Built-in grid utilities for responsive layouts:

```html
<div class="grid grid-cols grid-cols-sm-2 grid-cols-md-3">
  <!-- 1 column on mobile, 2 on tablet, 3 on desktop -->
</div>
```

### Responsive Typography

Fluid typography using clamp():

```css
--font-size-responsive-sm: clamp(var(--font-size-xs), 2vw, var(--font-size-sm))
--font-size-responsive-md: clamp(var(--font-size-sm), 2.5vw, var(--font-size-md))
--font-size-responsive-lg: clamp(var(--font-size-md), 3vw, var(--font-size-lg))
```

### Responsive Spacing

Fluid spacing that scales with viewport:

```css
--spacing-responsive-sm: clamp(var(--spacing-xs), 2vw, var(--spacing-sm))
--spacing-responsive-md: clamp(var(--spacing-sm), 3vw, var(--spacing-md))
--spacing-responsive-lg: clamp(var(--spacing-md), 4vw, var(--spacing-lg))
```

### Utility Classes

#### Responsive Display

```css
.hide-sm  /* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
/* Hidden on mobile */
.hide-md  /* Hidden on tablet */
.hide-lg; /* Hidden on desktop */
```

#### Responsive Text Alignment

```css
.text-sm-left   /* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
/* Left-aligned on mobile */
.text-sm-center /* Center-aligned on mobile */
.text-sm-right  /* Right-aligned on mobile */
.text-md-left; /* Left-aligned on tablet */
/* etc... */
```

### Best Practices

1. **Mobile-First Development**

   - Start with mobile layout
   - Add complexity for larger screens
   - Use min-width media queries

2. **Container Usage**

   ```css
   .section {
     @extend .container;
     /* Additional styles */
   }
   ```

3. **Grid Implementation**

   ```css
   .dashboard {
     display: grid;
     gap: var(--spacing-responsive-sm);
     grid-template-columns: 1fr;

     @media (min-width: var(--breakpoint-md)) {
       grid-template-columns: repeat(3, 1fr);
     }
   }
   ```

4. **Responsive Typography**

   ```css
   .title {
     font-size: var(--font-size-responsive-lg);
   }
   ```

5. **Responsive Spacing**
   ```css
   .card {
     padding: var(--spacing-responsive-sm);
     margin-bottom: var(--spacing-responsive-md);
   }
   ```

### Example Implementation

```html
<div class="dashboard-section container">
  <div class="grid grid-cols grid-cols-sm-2 grid-cols-md-3">
    <div class="metric-card spacing-responsive">
      <h2 class="card-title">Metric</h2>
      <p class="card-details hide-sm">Details</p>
      <div class="card-footer text-sm-center text-md-left">Footer</div>
    </div>
  </div>
</div>
```

```css
.metric-card {
  background: var(--background);
  border-radius: var(--radius-md);
  padding: var(--spacing-responsive-md);
}

.card-title {
  font-size: var(--font-size-responsive-md);
  margin-bottom: var(--spacing-responsive-sm);
}

.card-details {
  font-size: var(--font-size-responsive-sm);
}
```

### Converting Existing Components

1. **Replace Fixed Widths**

   - Before:
     ```css
     .section {
       width: 1200px;
     }
     ```
   - After:
     ```css
     .section {
       @extend .container;
     }
     ```

2. **Use Grid System**

   - Before:
     ```css
     .cards {
       display: flex;
       flex-wrap: wrap;
     }
     .card {
       width: 33.33%;
     }
     ```
   - After:
     ```html
     <div class="grid grid-cols grid-cols-sm-2 grid-cols-md-3"></div>
     ```

3. **Apply Utility Classes**

   - Before:
     ```html
     <div style="text-align: left;"></div>
     ```
   - After:
     ```html
     <div class="text-sm-center text-md-left"></div>
     ```

4. **Use Responsive Variables**

   - Before:
     ```css
     padding: 20px;
     margin: 30px;
     ```
   - After:
     ```css
     padding: var(--spacing-responsive-sm);
     margin: var(--spacing-responsive-md);
     ```

5. **Implement Fluid Typography**
   - Before:
     ```css
     font-size: 24px;
     @media (max-width: 768px) {
       font-size: 20px;
     }
     ```
   - After:
     ```css
     font-size: var(--font-size-responsive-lg);
     ```
