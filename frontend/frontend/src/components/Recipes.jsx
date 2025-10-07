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
    <div className="pt-20 max-w-3xl mx-auto p-6">
      <h2 className="text-3xl font-bold mb-6 text-center text-white-800">
        🍳 Create a Recipe!
      </h2>

      <div className="mb-6">
        <CreateRecipeForm createRecipe={createRecipe} />
      </div>

      {isSearching && (
        <div className="flex items-center justify-center space-x-3 mt-4">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
          <span className="text-white-800 font-semibold">
            Generating your recipe...
          </span>
        </div>
      )}

      {recipeData && (
        <>
          {/* Recipe Card */}
          <div className="bg-white shadow-lg rounded-2xl p-6 mb-6 border border-gray-100 text-left">
            <h3 className="text-2xl font-semibold text-gray-800 mb-3">
              {recipeData.title}
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-gray-700 mb-4">
              <p>
                <span className="font-semibold">🍽 Serving Size:</span>{" "}
                {recipeData.serving_size}
              </p>
              <p>
                <span className="font-semibold">🕒 Prep Time:</span>{" "}
                {recipeData.prep_time} min
              </p>
              <p>
                <span className="font-semibold">🔥 Cook Time:</span>{" "}
                {recipeData.cook_time} min
              </p>
            </div>

            <div className="mb-4">
              <h4 className="text-lg font-semibold text-gray-800 mb-2">
                🧂 Ingredients
              </h4>
              <p className="whitespace-pre-line text-gray-700 leading-relaxed">
                {recipeData.ingredients}
              </p>
            </div>

            <div className="mb-4">
              <h4 className="text-lg font-semibold text-gray-800 mb-2">
                👩‍🍳 Instructions
              </h4>
              <p className="whitespace-pre-line text-gray-700 leading-relaxed">
                {recipeData.instructions}
              </p>
            </div>
          </div>

          {/* Sources Card */}
          {recipeData.url?.length > 0 && (
            <div className="bg-white shadow-lg rounded-2xl p-6 border border-gray-100 text-left">
              <h4 className="text-lg font-semibold text-gray-800 mb-2">
                🌐 Sources
              </h4>
              <ul className="list-disc list-inside text-blue-600">
                {recipeData.url.map((u, i) => (
                  <li key={i}>
                    <a
                      href={u}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {u}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default Recipe;