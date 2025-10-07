import React, { useState } from 'react';

const CreateRecipeForm = ({ createRecipe }) => {
  const [recipeName, setRecipeName] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    if (recipeName) {
      createRecipe(recipeName);
      setRecipeName('');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={recipeName}
        onChange={(e) => setRecipeName(e.target.value)}
        placeholder="Enter recipe name"
        className="flex-1 p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400 text-lg"
      />
      <button className="ml-4 px-5 py-3 bg-blue-500 text-white font-semibold rounded-md hover:bg-blue-600 transition-colors duration-200" type="submit">Create</button>
    </form>
  );
};

export default CreateRecipeForm;