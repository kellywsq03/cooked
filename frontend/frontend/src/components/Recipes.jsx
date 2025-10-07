import React, {useState} from 'react';
import api from "../api.js";
import CreateRecipeForm from './CreateRecipeForm.jsx';

const Recipe = () => {
    const [recipeData, setRecipeData] = useState(null)
    const [isSearching, setIsSearching] = useState(false)

  const createRecipe = async (recipeName) => {
    try {
        setIsSearching(true);
        const response = await api.post('/', {"recipe": recipeName });
        setRecipeData(response.data.result);
        setIsSearching(false);
    } catch (error) {
      console.error("Error getting recipe", error);
      setIsSearching(false);
    }
  };

  return (
    <div>
      <h2>Create a recipe!</h2>
      <CreateRecipeForm createRecipe={createRecipe} />
      {isSearching && 
      <div className="flex items-center space-x-2 mt-3">
          <div className="animate-spin rounded-full h-6 w-6 border-4 border-blue-500 border-b-transparent" />
          <span>Indexing in progress...</span>
      </div>
      }
      {recipeData && (
        <div style={{ marginTop: "2rem" }}>
          <h3>{recipeData.title}</h3>
          <p><strong>Serving Size:</strong> {recipeData.serving_size}</p>
          <p><strong>Prep Time:</strong> {recipeData.prep_time} minutes</p>
          <p><strong>Cook Time:</strong> {recipeData.cook_time} minutes</p>
          <p><strong>Ingredients:</strong><br />{recipeData.ingredients}</p>
          <p><strong>Instructions:</strong><br />{recipeData.instructions}</p>
          {recipeData.url?.length > 0 && (
            <div>
              <strong>Sources:</strong>
              <ul>
                {recipeData.url.map((u, i) => (
                  <li key={i}><a href={u} target="_blank" rel="noopener noreferrer">{u}</a></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Recipe;