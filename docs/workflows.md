# Common CLI Workflows & Examples

Real-world examples of how agents typically use pkanban for common scenarios.

## 🎯 Workflow: Setting Up a New Project Board

```bash
# 1. Create the main project board
pkanban board create "Website Redesign"
# Output: Board created with id=5

# 2. View the board to see default columns
pkanban board get 5
# Output shows default columns with IDs

# 3. Create custom workflow columns
pkanban column create 5 "Backlog" 0
pkanban column create 5 "Sprint Planning" 1  
pkanban column create 5 "In Progress" 2
pkanban column create 5 "Code Review" 3
pkanban column create 5 "Testing" 4
pkanban column create 5 "Done" 5

# 4. Add some initial tasks
pkanban card create 1 "Research competitors" --description "Analyze top 3 competitor sites" --position 0
pkanban card create 1 "Create wireframes" --description "Mobile-first design" --position 1
pkanban card create 1 "Set up repository" --description "Git repo with CI/CD" --position 2
```

## 👥 Workflow: Team Collaboration Setup

```bash
# 1. Create organization
pkanban org create "Acme Corp"
# Output: Organization created with id=3

# 2. Create development team
pkanban team create 3 "Frontend Team"
# Output: Team created with id=7

# 3. Add team members
pkanban org member-add 3 alice
pkanban org member-add 3 bob  
pkanban org member-add 3 charlie

pkanban team member-add 7 alice
pkanban team member-add 7 bob

# 4. Share board with team
pkanban share 5 7
# Output: Board 5 shared with team 7

# 5. Verify setup
pkanban org get 3
pkanban team get 7
pkanban board list  # Should show shared boards
```

## 🔄 Workflow: Daily Sprint Management

```bash
# Morning: Check current board state
pkanban board get 5

# Move cards to "In Progress"
pkanban card update 12 "Research competitors" --column 2 --position 0
pkanban card update 13 "Create wireframes" --column 2 --position 1

# During day: Update card details
pkanban card update 12 "Research competitors - DONE" --description "Analyzed top 3 competitor sites, found key patterns"

# Move completed cards to "Done"
pkanban card update 12 "Research competitors - DONE" --column 5 --position 0
```

## 🏗️ Workflow: Multi-Project Organization

```bash
# 1. Create organization
pkanban org create "Digital Agency"
# Output: Organization created with id=4

# 2. Create multiple teams
pkanban team create 4 "Design Team"
pkanban team create 4 "Development Team"  
pkanban team create 4 "Marketing Team"

# 3. Create project boards
pkanban board create "Website Redesign"
pkanban board create "Mobile App"
pkanban board create "Brand Campaign"

# 4. Share boards with appropriate teams
pkanban share 6 8  # Website with Design Team
pkanban share 7 9  # Mobile App with Dev Team  
pkanban share 8 10 # Campaign with Marketing Team

# 5. Some boards need multiple teams
# (Note: sharing is not additive, so pick primary team)
```

## 🚀 Workflow: Rapid Prototyping Board

```bash
# Quick board for prototype ideas
pkanban board create "Prototype Ideas"

# Simple 3-column setup
pkanban column create 9 "Ideas" 0
pkanban column create 9 "Prototyping" 1  
pkanban column create 9 "Test Results" 2

# Rapid card creation
pkanban card create 1 "AI Chatbot" --description "Explore OpenAI integration" --position 0
pkanban card create 1 "Dark Mode Toggle" --description "CSS variables approach" --position 1
pkanban card create 1 "Drag & Drop" --description "Native HTML5 drag API" --position 2
pkanban card create 1 "Real-time Updates" --description "WebSocket implementation" --position 3
```

## 📊 Workflow: Board Cleanup & Reorganization

```bash
# 1. Check current board
pkanban board get 5

# 2. Move all cards from old column to new column
# (First, get card IDs from board output)
pkanban card update 15 "Old task" --column 8 --position 0
pkanban card update 16 "Another task" --column 8 --position 1

# 3. Delete unused columns
pkanban column delete 4

# 4. Reorder columns by updating positions
# (This requires API calls or recreation - simpler to recreate)
```

## 🔍 Workflow: Investigation & Debugging

```bash
# When something isn't working:

# 1. Check configuration
pkanban config
# Should show: Server URL: https://pkanban.pearachute.com

# 2. Verify login status
pkanban board list
# If error: "Not logged in" - then:
pkanban login myuser --password mypass

# 3. Check what you can access
pkanban board list
pkanban org list

# 4. Inspect specific resources
pkanban board get 5
pkanban org get 3
pkanban team get 7

# 5. Test permissions
pkanban share 5 private
pkanban share 5 7
```

## 🎪 Workflow: Demo Environment Setup

```bash
# Quick demo board for presentations
pkanban board create "Demo Project"

# Demo columns
pkanban column create 11 "📋 Planning" 0
pkanban column create 11 "🚀 In Progress" 1
pkanban column create 11 "✅ Review" 2
pkanban column create 11 "🎉 Done" 3

# Demo cards with emojis in titles
pkanban card create 1 "📊 User Research" --description "Interview 5 users" --position 0
pkanban card create 1 "🎨 Design Mockups" --description "Create Figma designs" --position 1
pkanban card create 1 "⚙️ API Integration" --description "Connect to backend" --position 2

# Share with demo team
pkanban share 11 12
```

## 🔄 Workflow: Board Archival

```bash
# When a project is complete:

# 1. Mark board clearly
pkanban board update 15 "COMPLETED: Website Redesign"

# 2. Make private to reduce clutter
pkanban share 15 private

# 3. Move completed cards to final column
pkanban board get 15  # Check current state
pkanban card update 45 "Final task" --column 6 --position 0

# Note: Actual archival might be done via web interface for bulk operations
```

## 💡 Tips for Agent Efficiency

1. **Batch operations**: Create all boards first, then all columns, then all cards
2. **Use consistent naming**: Prefix related items (`"PROJ: Task name"`)
3. **Document IDs**: Keep track of board/column IDs for scripts
4. **Test with small data**: Verify workflow with 1-2 cards before scaling
5. **Use board descriptions**: Update board names to indicate status
6. **Team sharing setup**: Configure org → teams → members → boards in order

## 🚨 Common Error Patterns

```bash
# Error: "Not logged in"
pkanban login username --password password

# Error: "Board not found"  
pkanban board list  # Check what boards exist

# Error: "Column not found"
pkanban board get <board-id>  # Get correct column IDs

# Error: "Team not found"
pkanban team list --org-id <org-id>  # Check available teams
```