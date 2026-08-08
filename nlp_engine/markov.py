import numpy as np

class MarkovCareerRecommender:
    def __init__(self, transitions_list=None):
        """
        transitions_list: list of dicts/tuples: (from_role, to_role, count)
        """
        self.transitions = {} # from_role -> {to_role: count}
        self.transition_matrix = {} # from_role -> {to_role: probability}
        
        if transitions_list:
            self.build_transition_matrix(transitions_list)

    def build_transition_matrix(self, transitions_list):
        """
        Builds the transition frequency dictionary and normalizes it to obtain probabilities.
        """
        self.transitions = {}
        for item in transitions_list:
            # item can be dict or object
            if isinstance(item, dict):
                from_role = item['from_role']
                to_role = item['to_role']
                count = item['count']
            else:
                from_role = item.from_state.name
                to_role = item.to_state.name
                count = item.transition_count
                
            if from_role not in self.transitions:
                self.transitions[from_role] = {}
            self.transitions[from_role][to_role] = self.transitions[from_role].get(to_role, 0) + count
            
        # Normalize to probabilities
        self.transition_matrix = {}
        for from_role, targets in self.transitions.items():
            total = sum(targets.values())
            if total > 0:
                self.transition_matrix[from_role] = {
                    to_role: count / total for to_role, count in targets.items()
                }
            else:
                self.transition_matrix[from_role] = {}

    def get_transitions_from(self, current_role):
        """
        Returns a dict of {to_role: probability} for the given role.
        """
        return self.transition_matrix.get(current_role, {})

    def calculate_skill_compatibility(self, user_skills, target_required_skills):
        """
        Calculates skill compatibility score as:
        Number of overlapping skills / Total required skills
        Returns a float between 0.0 and 1.0.
        """
        if not target_required_skills:
            return 1.0 # If no required skills, user matches 100%
            
        user_skills_set = {s.lower() for s in user_skills}
        required_skills_set = {s.lower() for s in target_required_skills}
        
        matched = user_skills_set.intersection(required_skills_set)
        return len(matched) / len(required_skills_set)

    def rank_next_roles(self, current_role, user_skills, user_embedding, 
                        job_roles_data, embedder_manager,
                        w_markov=0.50, w_skill=0.30, w_semantic=0.20):
        """
        Ranks all possible next career roles from the current state.
        
        job_roles_data: dict of {job_role_name: {required_skills: [...], embedding: [...]}}
        """
        possible_transitions = self.get_transitions_from(current_role)
        if not possible_transitions:
            # If no transitions are recorded in dataset, we fallback to all roles in job_roles_data (with 0.0 transition probability)
            possible_transitions = {role: 0.0 for role in job_roles_data.keys() if role != current_role}

        ranked_paths = []
        for to_role, prob in possible_transitions.items():
            role_info = job_roles_data.get(to_role)
            if not role_info:
                continue
                
            required_skills = role_info.get('required_skills', [])
            role_embedding = role_info.get('embedding')
            
            # 1. Transition probability
            p_transition = prob
            
            # 2. Skill compatibility
            skill_comp = self.calculate_skill_compatibility(user_skills, required_skills)
            
            # 3. Semantic similarity
            if embedder_manager is not None and role_embedding is not None and user_embedding is not None:
                semantic_comp = embedder_manager.calculate_similarity(user_embedding, role_embedding)
            else:
                semantic_comp = 0.5 # Default fallback
                
            # Configurable Career Score formula
            career_score = (w_markov * p_transition) + (w_skill * skill_comp) + (w_semantic * semantic_comp)
            
            ranked_paths.append({
                'role': to_role,
                'transition_probability': p_transition,
                'skill_compatibility': skill_comp,
                'semantic_compatibility': semantic_comp,
                'career_score': career_score
            })
            
        # Sort by career score descending
        ranked_paths.sort(key=lambda x: x['career_score'], reverse=True)
        return ranked_paths

    def generate_roadmap(self, current_role, user_skills, user_embedding, 
                         job_roles_data, embedder_manager, max_steps=3):
        """
        Generates a sequence of states representing a roadmap:
        Current Role -> Next Role -> Future Role -> Advanced Role
        """
        path = []
        visited = {current_role}
        curr = current_role
        
        for step in range(max_steps):
            # Rank the next roles from the current node
            candidates = self.rank_next_roles(
                current_role=curr, 
                user_skills=user_skills, 
                user_embedding=user_embedding, 
                job_roles_data=job_roles_data,
                embedder_manager=embedder_manager,
                w_markov=0.50, # Use standard weights for progression
                w_skill=0.30,
                w_semantic=0.20
            )
            
            # Filter out already visited roles to prevent cycles
            candidates = [c for c in candidates if c['role'] not in visited]
            
            if not candidates:
                break
                
            next_best = candidates[0] # Highest ranked candidate
            path.append(next_best)
            curr = next_best['role']
            visited.add(curr)
            
            # Update user_skills/embedding to simulate progress?
            # For simplicity, we assume the user gains some of the skills, 
            # but we can keep their current skills to evaluate gap at each step.
            
        return path
